import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.K6_BASE_URL || 'http://localhost:8000';
const STRESS_USERS = Number(__ENV.K6_VUS || 10);
const DURATION = __ENV.K6_DURATION || '30s';

export const options = {
  vus: STRESS_USERS,
  duration: DURATION,
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<750'],
  },
};

export default function () {
  const res = http.get(`${BASE_URL}/api/events?page=1&page_size=10`);
  check(res, {
    'status 200': (r) => r.status === 200,
    'has items array': (r) => r.json('items') !== undefined,
  });

  const rec = http.get(`${BASE_URL}/api/events/recommended?page=1&page_size=5`, {
    headers: { Authorization: __ENV.K6_TOKEN ? `Bearer ${__ENV.K6_TOKEN}` : '' },
  });
  check(rec, {
    'rec returns 200/401': (r) => r.status === 200 || r.status === 401,
  });

  sleep(1);
}
