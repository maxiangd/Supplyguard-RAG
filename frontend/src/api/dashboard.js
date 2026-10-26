import client from './client';

export function fetchDashboard() {
  return client.get('/dashboard');
}