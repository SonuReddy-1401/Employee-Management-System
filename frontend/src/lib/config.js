// Development default port constants for local microservice monitoring tools
export const GRAFANA_PORT = 3000;
export const PROMETHEUS_PORT = 9090;
export const RABBITMQ_PORT = 15672;

export function getToolLinks() {
  const host = typeof window !== 'undefined' && window.location ? window.location.hostname : 'localhost';
  const protocol = typeof window !== 'undefined' && window.location ? window.location.protocol : 'http:';

  return {
    grafana: `${protocol}//${host}:${GRAFANA_PORT}`,
    prometheus: `${protocol}//${host}:${PROMETHEUS_PORT}`,
    rabbitmq: `${protocol}//${host}:${RABBITMQ_PORT}`,
  };
}
