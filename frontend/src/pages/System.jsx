import React, { useState, useEffect, useCallback } from 'react';
import { getToolLinks } from '../lib/config.js';
import { Badge } from '../components/Badge.jsx';
import { Spinner } from '../components/Spinner.jsx';

export function System() {
  const [services, setServices] = useState({
    auth: { status: 'checking', timeMs: null },
    employee: { status: 'checking', timeMs: null },
    leave: { status: 'checking', timeMs: null },
    payroll: { status: 'checking', timeMs: null },
    notification: { status: 'checking', timeMs: null },
    gateway: { status: 'checking', timeMs: null },
  });
  const [checking, setChecking] = useState(false);

  const toolLinks = getToolLinks();

  const checkServices = useCallback(async () => {
    setChecking(true);
    const serviceList = ['auth', 'employee', 'leave', 'payroll', 'notification', 'gateway'];

    const newStatuses = {};

    await Promise.all(
      serviceList.map(async (svc) => {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        const startTime = Date.now();

        try {
          // Unauthenticated status route via Nginx
          const response = await fetch(`/status/${svc}`, {
            signal: controller.signal,
          });
          clearTimeout(timeoutId);
          const timeMs = Date.now() - startTime;

          if (response.status === 200) {
            newStatuses[svc] = { status: 'UP', timeMs };
          } else {
            newStatuses[svc] = { status: 'DOWN', timeMs };
          }
        } catch (err) {
          clearTimeout(timeoutId);
          const timeMs = Date.now() - startTime;
          newStatuses[svc] = { status: 'DOWN', timeMs };
        }
      })
    );

    setServices(newStatuses);
    setChecking(false);
  }, []);

  useEffect(() => {
    checkServices();
  }, [checkServices]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h1 className="card-title" style={{ margin: 0 }}>
            System Status & Logs
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Microservice health status checks and telemetry links.
          </p>
        </div>

        <button
          className="btn btn-primary"
          onClick={checkServices}
          disabled={checking}
          data-testid="check-system-now-btn"
        >
          {checking ? 'Checking...' : 'Check Now'}
        </button>
      </div>

      {/* Services Status Table */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h2 className="card-title" style={{ fontSize: '1rem', marginBottom: '1rem' }}>
          Microservice Health Checks
        </h2>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Service Name</th>
                <th>Endpoint</th>
                <th>Status</th>
                <th>Response Time</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(services).map(([name, info]) => (
                <tr key={name}>
                  <td style={{ textTransform: 'capitalize', fontWeight: 600 }}>{name} Service</td>
                  <td><code>/status/{name}</code></td>
                  <td>
                    {info.status === 'checking' ? (
                      <Spinner />
                    ) : (
                      <Badge type={info.status === 'UP' ? 'active' : 'failed'}>{info.status}</Badge>
                    )}
                  </td>
                  <td>{info.timeMs !== null ? `${info.timeMs} ms` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Development Telemetry & Monitoring Tools */}
      <div className="card">
        <h2 className="card-title" style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>
          Infrastructure Monitoring Tools
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '1rem' }}>
          Quick links to local development monitoring tools (using development default ports).
        </p>

        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <a
            href={toolLinks.grafana}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary"
            style={{ textDecoration: 'none' }}
            data-testid="grafana-link"
          >
            Grafana Dashboards ↗ (Port 3000)
          </a>

          <a
            href={toolLinks.prometheus}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary"
            style={{ textDecoration: 'none' }}
            data-testid="prometheus-link"
          >
            Prometheus Metrics ↗ (Port 9090)
          </a>

          <a
            href={toolLinks.rabbitmq}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-secondary"
            style={{ textDecoration: 'none' }}
            data-testid="rabbitmq-link"
          >
            RabbitMQ Management ↗ (Port 15672)
          </a>
        </div>
      </div>
    </div>
  );
}
