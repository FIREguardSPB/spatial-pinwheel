import unittest
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from core.models import schemas
from core.services import settings_presets as presets_service
from core.storage.models import SettingsPreset, Watchlist
from core.storage.repos import settings as settings_repo

class FakeQuery:
    def __init__(self, rows): self._rows = rows
    def all(self): return list(self._rows)
    def first(self): return self._rows[0] if self._rows else None

class FakeDB:
    def __init__(self): self.storage = {SettingsPreset: [], Watchlist: []}; self.commits = 0
    def query(self, model): return FakeQuery(self.storage.setdefault(model, []))
    def add(self, row): self.storage.setdefault(type(row), []).append(row)
    def delete(self, row): self.storage.setdefault(type(row), []).remove(row)
    def commit(self): self.commits += 1
    def refresh(self, row): return row

class SettingsPresetRepoTests(unittest.TestCase):
    def test_create_update_delete_user_preset(self):
        db = FakeDB()
        row, created = settings_repo.create_or_update_user_preset(db, preset_id='preset_user_alpha', name='Alpha', description='First version', settings_json={'risk_profile': 'balanced'})
        self.assertTrue(created); self.assertEqual(row.name, 'Alpha'); self.assertEqual(len(settings_repo.list_presets(db)), 1)
        updated, created_again = settings_repo.create_or_update_user_preset(db, preset_id='preset_user_alpha_new', name='Alpha', description='Updated version', settings_json={'risk_profile': 'aggressive'})
        self.assertFalse(created_again); self.assertEqual(updated.description, 'Updated version'); self.assertEqual(updated.settings_json['risk_profile'], 'aggressive'); self.assertEqual(len(settings_repo.list_presets(db)), 1)
        self.assertTrue(settings_repo.delete_preset(db, row.id)); self.assertEqual(len(settings_repo.list_presets(db)), 0)

    def test_system_preset_cannot_be_overwritten_or_deleted(self):
        db = FakeDB(); settings_repo.ensure_system_presets(db, presets_service.build_system_presets())
        with self.assertRaises(ValueError): settings_repo.create_or_update_user_preset(db, preset_id='preset_user_balanced_copy', name='Balanced', description='Collision', settings_json={'risk_profile': 'balanced'})
        with self.assertRaises(PermissionError): settings_repo.delete_preset(db, 'preset_system_balanced')

    def test_apply_merge_preserves_runtime_only_fields_and_updates_watchlist(self):
        current = schemas.RiskSettings(risk_profile='balanced', risk_per_trade_pct=0.25, daily_loss_limit_pct=1.5, max_concurrent_positions=4, max_trades_per_day=120, rr_target=1.4, time_stop_bars=12, close_before_session_end_minutes=5, telegram_bot_token='secret-token', telegram_chat_id='123', trade_mode='auto_paper').model_dump(mode='json')
        snapshot = presets_service.validate_snapshot_payload({'risk_profile': 'conservative', 'trade_mode': 'review', 'watchlist': ['TQBR:SBER', 'GAZP']})
        validated = schemas.RiskSettings(**presets_service.merge_snapshot_into_settings(current, snapshot))
        self.assertEqual(validated.risk_profile, 'conservative'); self.assertEqual(validated.trade_mode, 'review'); self.assertEqual(validated.telegram_bot_token, 'secret-token'); self.assertEqual(validated.telegram_chat_id, '123')
        db = FakeDB(); db.storage[Watchlist] = [Watchlist(instrument_id='TQBR:SBER', ticker='SBER', name='SBER', exchange='TQBR', is_active=True, added_ts=1), Watchlist(instrument_id='TQBR:LKOH', ticker='LKOH', name='LKOH', exchange='TQBR', is_active=True, added_ts=1)]
        diff = presets_service.apply_watchlist_snapshot(db, snapshot['watchlist'])
        self.assertEqual(diff['added'], ['TQBR:GAZP']); self.assertEqual(diff['removed'], ['TQBR:LKOH']); self.assertIn('TQBR:SBER', diff['kept'])

class PresetCreateBody(BaseModel):
    name: str
    description: str = ''

class SettingsPresetApiTests(unittest.TestCase):
    def setUp(self):
        self.db = FakeDB(); settings_repo.ensure_system_presets(self.db, presets_service.build_system_presets())
        self.current_settings = schemas.RiskSettings(risk_profile='balanced', risk_per_trade_pct=0.25, daily_loss_limit_pct=1.5, max_concurrent_positions=4, max_trades_per_day=120, rr_target=1.4, time_stop_bars=12, close_before_session_end_minutes=5, telegram_bot_token='secret-token', trade_mode='auto_paper').model_dump(mode='json')
        self.current_watchlist = ['TQBR:SBER', 'TQBR:GAZP']
        app = FastAPI()
        @app.get('/presets')
        def list_presets(): return {'items': [{'id': row.id, 'name': row.name, 'description': row.description, 'settings_json': row.settings_json, 'created_at': row.created_at, 'updated_at': row.updated_at, 'is_system': row.is_system} for row in settings_repo.list_presets(self.db)]}
        @app.post('/presets')
        def create_preset(body: PresetCreateBody):
            snapshot = presets_service.build_snapshot_from_settings_dict(self.current_settings, self.current_watchlist)
            row, created = settings_repo.create_or_update_user_preset(self.db, preset_id=f'preset_{presets_service.slugify_preset_name(body.name)}', name=body.name, description=body.description, settings_json=snapshot)
            return {'preset': {'id': row.id, 'name': row.name, 'description': row.description, 'settings_json': row.settings_json, 'created_at': row.created_at, 'updated_at': row.updated_at, 'is_system': row.is_system}, 'created': created}
        @app.post('/presets/{preset_id}/apply')
        def apply_preset(preset_id: str):
            row = settings_repo.get_preset(self.db, preset_id)
            if row is None: raise HTTPException(status_code=404, detail='Preset not found')
            current_snapshot = presets_service.build_snapshot_from_settings_dict(self.current_settings, self.current_watchlist)
            schemas.RiskSettings(**presets_service.merge_snapshot_into_settings(self.current_settings, row.settings_json))
            watchlist_diff = presets_service.apply_watchlist_snapshot(self.db, row.settings_json.get('watchlist')) if 'watchlist' in row.settings_json else {'added': [], 'removed': [], 'kept': []}
            diff = presets_service.build_diff_summary(current_snapshot, row.settings_json); diff['watchlist'] = watchlist_diff
            return {'ok': True, 'preset': {'id': row.id, 'name': row.name}, 'applied': diff}
        @app.delete('/presets/{preset_id}')
        def delete_preset(preset_id: str):
            try: deleted = settings_repo.delete_preset(self.db, preset_id)
            except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc)) from exc
            if not deleted: raise HTTPException(status_code=404, detail='Preset not found')
            return {'ok': True, 'deleted': preset_id}
        self.client = TestClient(app)

    def test_list_presets_endpoint(self):
        resp = self.client.get('/presets'); self.assertEqual(resp.status_code, 200); payload = resp.json(); self.assertGreaterEqual(len(payload['items']), 3); self.assertTrue(any(item['is_system'] for item in payload['items']))
    def test_create_preset_endpoint(self):
        resp = self.client.post('/presets', json={'name': 'Alpha', 'description': 'Snapshot'}); self.assertEqual(resp.status_code, 200); payload = resp.json(); self.assertEqual(payload['preset']['name'], 'Alpha'); self.assertTrue(payload['created']); self.assertIn('watchlist', payload['preset']['settings_json']); self.assertNotIn('telegram_bot_token', payload['preset']['settings_json'])
    def test_apply_preset_endpoint(self):
        self.client.post('/presets', json={'name': 'Alpha', 'description': 'Snapshot'}); resp = self.client.post('/presets/preset_alpha/apply'); self.assertEqual(resp.status_code, 200); payload = resp.json(); self.assertTrue(payload['ok']); self.assertEqual(payload['preset']['id'], 'preset_alpha'); self.assertIn('changed_keys', payload['applied']); self.assertIn('watchlist', payload['applied'])
    def test_delete_user_preset_and_block_system_delete(self):
        self.client.post('/presets', json={'name': 'Alpha', 'description': 'Snapshot'}); self.assertEqual(self.client.delete('/presets/preset_alpha').status_code, 200); self.assertEqual(self.client.delete('/presets/preset_system_balanced').status_code, 403)

if __name__ == '__main__':
    unittest.main()
