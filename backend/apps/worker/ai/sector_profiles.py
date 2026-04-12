
from __future__ import annotations

from dataclasses import dataclass

from apps.worker.ai.relevance import (
    should_include_fx_context,
    should_include_geopolitical_context,
    should_include_rate_context,
)
from apps.worker.ai.types import InternetContext


@dataclass(frozen=True)
class SectorProfile:
    code: str
    name_ru: str
    description: str
    tickers: frozenset[str]
    sector_keywords: tuple[str, ...]
    driver_hints: tuple[str, ...]


_GENERAL_PROFILE = SectorProfile(
    code="general",
    name_ru="широкий рынок",
    description="Общий рыночный профиль без выраженной отраслевой специфики.",
    tickers=frozenset(),
    sector_keywords=("market", "рынок", "equity", "stocks", "акции"),
    driver_hints=("ключевая ставка", "курс рубля", "геополитика", "ликвидность рынка"),
)

_PROFILES: tuple[SectorProfile, ...] = (
    SectorProfile(
        code="oil_gas",
        name_ru="нефтегаз",
        description="Экспортная сырьевая история с чувствительностью к Brent и логистике.",
        tickers=frozenset({"ROSN", "LKOH", "NVTK", "GAZP", "TATN", "SIBN", "SNGS"}),
        sector_keywords=(
            "brent", "oil", "нефть", "gas", "газ", "lng", "opec", "pipeline", "экспорт нефти",
            "газовый экспорт", "добыча", "переработка", "upstream", "downstream",
        ),
        driver_hints=("Brent", "санкции", "экспортные маршруты", "USD/RUB"),
    ),
    SectorProfile(
        code="banks_finance",
        name_ru="банки и финансовая инфраструктура",
        description="Чувствительны к ключевой ставке, ликвидности, качеству кредитного портфеля и санкциям.",
        tickers=frozenset({"SBER", "VTBR", "CBOM", "MOEX", "SFIN"}),
        sector_keywords=(
            "bank", "банки", "loan", "кредит", "mortgage", "ипотек", "deposit", "депозит",
            "exchange", "биржа", "brokerage", "брокер", "liquidity", "ликвидность",
        ),
        driver_hints=("ключевая ставка", "кредитный спрос", "ликвидность", "санкции"),
    ),
    SectorProfile(
        code="technology",
        name_ru="технологии и интернет",
        description="Зависят от ставки, спроса на цифровые сервисы, импорта оборудования и регуляторики.",
        tickers=frozenset({"YNDX", "VKCO"}),
        sector_keywords=(
            "technology", "internet", "ad market", "digital", "cloud", "software", "ai", "tech",
            "интернет", "технолог", "реклама", "облак", "софт", "цифров", "маркетплейс",
        ),
        driver_hints=("ставка", "digital/ad market", "регуляторика", "импорт оборудования"),
    ),
    SectorProfile(
        code="telecom",
        name_ru="телеком",
        description="Защитный сектор, но чувствителен к CAPEX, тарифам и валюте закупки оборудования.",
        tickers=frozenset({"MTSS", "RTKM"}),
        sector_keywords=(
            "telecom", "mobile", "broadband", "network", "subscriber", "spectrum", "5g",
            "телеком", "связь", "мобил", "широкополосн", "сеть", "абонент", "тариф",
        ),
        driver_hints=("CAPEX", "тарифы", "курс рубля", "потребительская устойчивость"),
    ),
    SectorProfile(
        code="transport",
        name_ru="транспорт и логистика",
        description="Зависят от топлива, маршрутов, санкций, страхования и спроса на перевозки.",
        tickers=frozenset({"AFLT", "FLOT", "FESH", "NMTP", "TRNFP"}),
        sector_keywords=(
            "transport", "aviation", "airline", "cargo", "freight", "logistics", "route", "jet fuel",
            "транспорт", "авиа", "перевозк", "логист", "маршрут", "грузо", "топливо",
        ),
        driver_hints=("топливо", "маршруты", "санкции", "спрос на перевозки"),
    ),
    SectorProfile(
        code="retail_ecommerce",
        name_ru="ритейл и e-commerce",
        description="Чувствительны к потребительскому спросу, инфляции, логистике и импортным издержкам.",
        tickers=frozenset({"MGNT", "OZON", "FIXP"}),
        sector_keywords=(
            "retail", "consumer", "ecommerce", "marketplace", "grocery", "demand", "warehouse",
            "ритейл", "потребител", "маркетплейс", "продаж", "магазин", "склад", "доставка",
        ),
        driver_hints=("потребительский спрос", "инфляция", "логистика", "курс рубля"),
    ),
    SectorProfile(
        code="metals_mining",
        name_ru="металлы и добыча",
        description="Зависят от цен на сырьё, экспортных маршрутов, курса рубля и санкционного режима.",
        tickers=frozenset({"GMKN", "ALRS", "PLZL", "POLY"}),
        sector_keywords=(
            "mining", "metal", "gold", "nickel", "palladium", "diamond", "ore", "smelter",
            "добыч", "металл", "золото", "никель", "паллад", "алмаз", "руда",
        ),
        driver_hints=("цены на металлы", "экспорт", "USD/RUB", "санкции"),
    ),
    SectorProfile(
        code="utilities",
        name_ru="электроэнергетика и сети",
        description="Защитный внутренний сектор, чувствителен к тарифам, CAPEX и ставкам.",
        tickers=frozenset({"FEES", "HYDR"}),
        sector_keywords=(
            "utility", "power", "electricity", "grid", "hydro", "generation", "tariff",
            "энергет", "электро", "сети", "гидро", "генерац", "тариф",
        ),
        driver_hints=("тарифы", "CAPEX", "ставка", "защитный спрос"),
    ),
    SectorProfile(
        code="real_estate",
        name_ru="девелоперы и недвижимость",
        description="Сильно зависят от ключевой ставки, ипотеки и доступности финансирования.",
        tickers=frozenset({"PIKK", "SMLT"}),
        sector_keywords=(
            "real estate", "developer", "housing", "mortgage", "property", "construction",
            "девелоп", "недвижим", "жилье", "ипотек", "стройк", "квартир",
        ),
        driver_hints=("ипотека", "ключевая ставка", "спрос на жильё", "господдержка"),
    ),
    SectorProfile(
        code="fertilizers_agro",
        name_ru="удобрения и агро",
        description="Зависят от экспортной логистики, цен на продовольствие и курса рубля.",
        tickers=frozenset({"PHOR", "AGRO"}),
        sector_keywords=(
            "fertilizer", "grain", "crop", "food", "agro", "harvest", "export crop",
            "удобрени", "зерн", "урожай", "агро", "продовольств", "сельхоз",
        ),
        driver_hints=("экспорт", "логистика", "цены на продовольствие", "USD/RUB"),
    ),
    SectorProfile(
        code="forestry_packaging",
        name_ru="лес и упаковка",
        description="Экспортная история с чувствительностью к логистике, санкциям и валюте.",
        tickers=frozenset({"SGZH"}),
        sector_keywords=(
            "timber", "pulp", "paper", "packaging", "wood", "lumber",
            "лес", "пиломатериал", "целлюлоз", "бумаг", "упаковк",
        ),
        driver_hints=("экспорт", "логистика", "курс рубля", "санкции"),
    ),
)


def instrument_code(instrument_id: str) -> str:
    return instrument_id.split(":")[-1].upper()


def get_sector_profile(ticker_or_instrument: str) -> SectorProfile:
    ticker = instrument_code(ticker_or_instrument)
    for profile in _PROFILES:
        if ticker in profile.tickers:
            return profile
    return _GENERAL_PROFILE


def sector_keywords_for_ticker(ticker_or_instrument: str) -> list[str]:
    profile = get_sector_profile(ticker_or_instrument)
    return list(profile.sector_keywords)


def sector_driver_summary(ticker_or_instrument: str) -> str:
    profile = get_sector_profile(ticker_or_instrument)
    return ", ".join(profile.driver_hints)


def _count(inet: InternetContext, key: str) -> int:
    return inet.topic_counts.get(key, 0) if inet.topic_counts else 0


def build_sector_company_context(ticker_or_instrument: str, inet: InternetContext, *, horizon: str = "scalp") -> list[str]:
    ticker = instrument_code(ticker_or_instrument)
    profile = get_sector_profile(ticker)
    brent = inet.macro.brent_usd
    usd_rub = inet.macro.usd_rub
    cbr = inet.macro.cbr_key_rate
    war_count = _count(inet, "война/конфликт")
    sanctions_count = _count(inet, "санкции")
    oil_count = _count(inet, "нефть/логистика")
    inflation_count = _count(inet, "ставки/инфляция")
    trade_count = _count(inet, "пошлины/торговля")
    include_rate = should_include_rate_context(profile.code, inet, horizon=horizon)
    include_geo = should_include_geopolitical_context(profile.code, inet, horizon=horizon)
    include_fx = should_include_fx_context(profile.code, inet, horizon=horizon)
    lines: list[str] = []

    if profile.code == "oil_gas":
        if brent is not None:
            if brent >= 100:
                lines.append(f"ПОЗИТИВНО: Brent=${brent:.2f} — высокая нефть поддерживает внутридневной спрос и экспортную выручку {ticker}.")
            elif brent <= 70:
                lines.append(f"НЕГАТИВНО: Brent=${brent:.2f} — слабая нефть ухудшает краткосрочный фон для нефтегаза.")
            else:
                lines.append(f"НЕЙТРАЛЬНО: Brent=${brent:.2f} — нефть без экстремума, эффект для {ticker} умеренный.")
        if include_geo and war_count:
            lines.append(f"ДИНАМИКА: {war_count} свежих geo/oil headline'ов усиливают волатильность и headline-risk для {ticker}.")
        if include_geo and (sanctions_count or oil_count):
            lines.append(f"РИСК: санкции/логистика ({sanctions_count + oil_count} свежих упоминаний) могут быстро влиять на экспортные маршруты и дисконты.")

    elif profile.code == "banks_finance":
        if include_rate and cbr is not None:
            lines.append(f"ДИНАМИКА: свежий rate-катализатор делает ставку {cbr:.2f}% актуальной для банков и ликвидности рынка.")
        if ticker == "MOEX" and inet.geopolitical_risk >= 0.6:
            lines.append("ПОЗИТИВНО/СМЕШАННО: повышенная волатильность может поддерживать обороты и комиссионные MOEX.")
        if include_geo and sanctions_count:
            lines.append(f"РИСК: свежий санкционный фон ({sanctions_count} headlines) влияет на расчёты и риск-премию финсектора.")

    elif profile.code == "technology":
        if include_rate and cbr is not None:
            lines.append(f"ДИНАМИКА: rate-катализатор усиливает чувствительность tech-сектора к ставке {cbr:.2f}%.")
        if include_fx and usd_rub is not None and usd_rub >= 95:
            lines.append(f"РИСК: свежий FX-шум при USD/RUB={usd_rub:.3f} повышает риск по импортному оборудованию и IT-CAPEX для {ticker}.")
        if include_geo and (sanctions_count or war_count):
            lines.append("РИСК: свежие геополитические headline'ы могут влиять на рекламу, экосистему и доступ к технологиям.")
        if inet.sentiment_score >= 0.15:
            lines.append(f"ПОЗИТИВНО: свежий digital/consumer tech фон поддерживает краткосрочный спрос на {ticker}.")

    elif profile.code == "telecom":
        if include_rate and cbr is not None:
            lines.append(f"ДИНАМИКА: rate-катализатор делает CAPEX-фактор по ставке {cbr:.2f}% релевантным и для телекома.")
        if include_fx and usd_rub is not None and usd_rub >= 95:
            lines.append(f"РИСК: свежий FX-фон при USD/RUB={usd_rub:.3f} удорожает импорт сетевого оборудования.")
        lines.append("ЗАЩИТНО: устойчивый внутренний спрос на связь частично смягчает внешний шум.")

    elif profile.code == "transport":
        if brent is not None and brent >= 95:
            lines.append(f"РИСК: Brent=${brent:.2f} повышает топливные издержки транспортных компаний.")
        if include_geo and (war_count or oil_count or trade_count):
            lines.append("РИСК: свежие geo/logistics headlines влияют на маршруты, страхование и пропускную способность.")
        if include_fx and usd_rub is not None and usd_rub >= 95:
            lines.append(f"РИСК: свежий FX-фон при USD/RUB={usd_rub:.3f} повышает стоимость лизинга, запчастей и сервиса.")

    elif profile.code == "retail_ecommerce":
        if include_rate and cbr is not None:
            lines.append(f"ДИНАМИКА: rate-катализатор делает ставку {cbr:.2f}% заметным фактором спроса в retail/e-commerce.")
        if inflation_count:
            lines.append(f"СМЕШАННО: свежий инфляционный фон ({inflation_count} упоминаний) поддерживает выручку номинально, но давит на маржу.")
        if include_fx and usd_rub is not None and usd_rub >= 95:
            lines.append(f"РИСК: свежий FX-фон при USD/RUB={usd_rub:.3f} повышает импортные и логистические издержки для {ticker}.")
        if include_geo and trade_count:
            lines.append("РИСК: торговые ограничения и сбои в поставках влияют на ассортимент и исполнение заказов.")

    elif profile.code == "metals_mining":
        if include_fx and usd_rub is not None and usd_rub >= 95:
            lines.append(f"ПОЗИТИВНО: свежий FX-фон при USD/RUB={usd_rub:.3f} поддерживает рублёвую экспортную выручку сырьевых компаний.")
        if include_geo and (sanctions_count or trade_count):
            lines.append("РИСК: свежие санкции/торговые ограничения влияют на экспортные каналы и дисконты на сырьё.")
        if ticker in {"PLZL", "POLY"} and inet.geopolitical_risk >= 0.7:
            lines.append("ПОЗИТИВНО/СМЕШАННО: risk-off может поддерживать золотодобытчиков как защитную историю.")

    elif profile.code == "utilities":
        if include_rate and cbr is not None:
            lines.append(f"ДИНАМИКА: rate-катализатор повышает чувствительность utilities к CAPEX и ставке {cbr:.2f}%.")
        lines.append("ЗАЩИТНО: внутренний спрос на электроэнергию делает сектор устойчивее к краткосрочному шуму.")

    elif profile.code == "real_estate":
        if include_rate and cbr is not None:
            if cbr >= 16:
                lines.append(f"НЕГАТИВНО: свежий rate-катализатор делает ставку {cbr:.2f}% реальным тормозом для ипотеки и спроса на жильё.")
            elif cbr <= 10:
                lines.append(f"ПОЗИТИВНО: свежий rate-катализатор делает ставку {cbr:.2f}% поддержкой ипотечного спроса.")
        lines.append("КЛЮЧЕВОЕ: для девелоперов в скальпинге учитывай ставку только при свежем rate-headline, а не как постоянный стоп-фактор.")

    elif profile.code == "fertilizers_agro":
        if include_fx and usd_rub is not None and usd_rub >= 95:
            lines.append(f"ПОЗИТИВНО: свежий FX-фон при USD/RUB={usd_rub:.3f} поддерживает экспортную рублёвую выручку сектора.")
        if include_geo and (sanctions_count or trade_count):
            lines.append("РИСК: свежая экспортная/logistics повестка влияет на поставки и цены.")
        if ticker == "AGRO":
            lines.append("СМЕШАННО: продовольственная инфляция может поддерживать цены реализации, но усиливает чувствительность к издержкам.")

    elif profile.code == "forestry_packaging":
        if include_fx and usd_rub is not None and usd_rub >= 95:
            lines.append(f"ПОЗИТИВНО: свежий FX-фон при USD/RUB={usd_rub:.3f} помогает экспортной выручке лесопромышленного сектора.")
        if include_geo and (sanctions_count or trade_count):
            lines.append("РИСК: лес и упаковка чувствительны к логистике, санкциям и экспортным ограничениям.")

    else:
        if include_rate and cbr is not None:
            lines.append(f"СМЕШАННО: свежий rate-катализатор делает ставку {cbr:.2f}% релевантной для оценки и фондирования компании.")
        if include_fx and usd_rub is not None and usd_rub >= 95:
            lines.append(f"РИСК: свежий FX-фон при USD/RUB={usd_rub:.3f} усиливает валютную волатильность и импортные издержки.")

    return lines[:5]


def build_sector_causal_context(ticker_or_instrument: str, inet: InternetContext, *, horizon: str = "scalp") -> list[str]:
    profile = get_sector_profile(ticker_or_instrument)
    brent = inet.macro.brent_usd
    usd_rub = inet.macro.usd_rub
    lines: list[str] = []

    if profile.code == "oil_gas" and brent is not None and brent >= 95:
        lines.append("Для нефтегаза Brent — динамический драйвер intraday, а геополитику учитывай только когда есть свежий shock headline.")
    elif profile.code == "banks_finance":
        lines.append("Для банков ставка важна только при свежем rate-катализаторе; без него в скальпинге приоритет у техники и ликвидности.")
    elif profile.code == "technology":
        lines.append("Для техов не блокируй сигнал из-за статичной ставки/геополитики: в скальпинге важнее техника, liquidity и свежий company catalyst.")
    elif profile.code == "telecom":
        lines.append("Для телекома учитывай CAPEX и валюту только при свежем catalyst, а не как постоянный фон на каждый сигнал.")
    elif profile.code == "transport":
        lines.append("Для транспорта Brent и логистика релевантны intraday, но только как динамические драйверы расходов и маршрутов.")
    elif profile.code == "retail_ecommerce":
        lines.append("Для ритейла и маркетплейсов основной intraday-фокус — спрос, логистика и company news, а не общий макрошум.")
    elif profile.code == "metals_mining":
        lines.append("Для сырьевых экспортеров слабый рубль и сырьевые цены релевантны, но санкции учитывай только при свежем headline.")
    elif profile.code == "utilities":
        lines.append("Энергетика обычно защитнее рынка: в скальпинге приоритет у техники и потока ликвидности, а не у фонового макро.")
    elif profile.code == "real_estate":
        lines.append("Для девелоперов ставка важна, но использовать её как блокер можно только при свежем заседании/сигнале ЦБ.")
    elif profile.code == "fertilizers_agro":
        lines.append("Для агро и удобрений важны экспортные каналы и валюта, но только когда это свежий catalyst, а не статичная константа.")
    elif profile.code == "forestry_packaging":
        lines.append("Для лесопрома геополитика проявляется через логистику и экспорт, но не должна автоматически блокировать intraday-сигнал.")

    if usd_rub is not None and usd_rub >= 95 and should_include_fx_context(profile.code, inet, horizon=horizon):
        lines.append("Свежий FX-шум усиливает роль импортных затрат и валютной переоценки только для чувствительных секторов.")

    return lines[:3]


def build_sector_narrative_summary(ticker_or_instrument: str, inet: InternetContext, *, horizon: str = "scalp") -> list[str]:
    profile = get_sector_profile(ticker_or_instrument)
    lines = [f"Сектор {profile.name_ru}: ключевые драйверы — {', '.join(profile.driver_hints)}."]
    lines.extend(build_sector_company_context(ticker_or_instrument, inet, horizon=horizon)[:2])
    return lines[:3]
