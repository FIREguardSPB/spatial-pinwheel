/**
 * P7-04: Global Vitest setup.
 * Initialises MSW server for all tests.
 */
import { afterAll, afterEach, beforeAll } from 'vitest';
import { setupServer } from 'msw/node';
import { handlers } from '../mocks/handlers';

// Start MSW server
export const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
