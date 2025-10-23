# PazPaz Network Architecture

## Overview

The production deployment uses a **three-tier network isolation architecture** to ensure maximum security and compliance with HIPAA requirements. This design prevents unauthorized access to sensitive services while maintaining necessary communication paths.

## Network Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                         INTERNET                                 │
└────────────────────┬───────────────────────────┬─────────────────┘
                     │ Port 80                   │ Port 443
                     ↓ (HTTP)                    ↓ (HTTPS)
        ┌────────────────────────────────────────────────────┐
        │                     NGINX                          │
        │            (Reverse Proxy & Static Files)          │
        │                 Container: nginx                   │
        └──────────┬──────────────────────────┬──────────────┘
                   │                          │
    ┌──────────────┴──────────────┐ ┌────────┴──────────────┐
    │    FRONTEND NETWORK         │ │   BACKEND NETWORK     │
    │   (Public-facing)           │ │   (Internal Only)     │
    │   172.20.0.0/24            │ │   172.21.0.0/24       │
    └─────────────────────────────┘ └───┬──────────────┬────┘
                                         │              │
                              ┌──────────┴───┐     ┌───┴──────────┐
                              │     API      │     │  ARQ Worker  │
                              │  Container:  │     │  Container:  │
                              │     api      │     │  arq-worker  │
                              └──────┬───────┘     └───┬──────────┘
                                     │                  │
                          ┌──────────┴──────────────────┴──────────┐
                          │       DATABASE NETWORK                  │
                          │       (Internal Only)                   │
                          │       172.22.0.0/24                    │
                          └───┬──────────┬──────────┬──────────────┘
                              │          │          │
                    ┌─────────┴───┐ ┌───┴───┐ ┌───┴────┐
                    │ PostgreSQL  │ │ Redis │ │ MinIO  │
                    │ Container:  │ │  db   │ │  S3    │
                    │     db      │ │       │ │        │
                    └─────────────┘ └───────┘ └────────┘
```

## Network Definitions

### 1. Frontend Network (`frontend`)

- **Type**: Bridge network (exposed to host)
- **Subnet**: 172.20.0.0/24
- **Purpose**: Public-facing network for external access
- **Services**: nginx only
- **Security**:
  - Only network with host port mappings
  - SSL/TLS termination at nginx
  - Rate limiting implemented

### 2. Backend Network (`backend`)

- **Type**: Bridge network with `internal: true`
- **Subnet**: 172.21.0.0/24
- **Purpose**: Internal API communication
- **Services**: nginx, api, arq-worker
- **Security**:
  - Isolated from host network
  - No direct external access
  - All traffic routed through nginx

### 3. Database Network (`database`)

- **Type**: Bridge network with `internal: true`
- **Subnet**: 172.22.0.0/24
- **Purpose**: Restricted database access
- **Services**: api, arq-worker, db, redis, minio
- **Security**:
  - Most restricted network
  - No external access whatsoever
  - Only application services can connect

## Service Network Assignments

| Service | Networks | Exposed Ports | Purpose |
|---------|----------|---------------|---------|
| nginx | frontend, backend | 80, 443 | Reverse proxy, SSL termination |
| api | backend, database | None | Business logic, API endpoints |
| arq-worker | backend, database | None | Background tasks, scheduling |
| db | database | None | PostgreSQL database |
| redis | database | None | Cache and task queue |
| minio | database | None | S3-compatible object storage |

## Security Features

### Network Isolation

1. **Internal Networks**: Backend and database networks use `internal: true` flag
   - Prevents any external access
   - Docker manages firewall rules automatically
   - No port forwarding possible

2. **No Database Exposure**:
   - PostgreSQL, Redis, MinIO have NO exposed ports
   - Access only through application layer
   - Prevents direct database attacks

3. **Single Entry Point**:
   - All external traffic enters through nginx
   - SSL/TLS termination at edge
   - Centralized security policies

### Communication Flow

```
External Request → nginx (frontend network)
                     ↓
                   nginx (backend network)
                     ↓
                   API (backend network)
                     ↓
                   API (database network)
                     ↓
                   Database Services
```

### Network Policies

1. **Frontend Network**:
   - Accepts connections from internet
   - Rate limiting applied
   - DDoS protection at nginx level

2. **Backend Network**:
   - No external connections
   - Service-to-service communication only
   - Application-level authentication

3. **Database Network**:
   - Most restrictive policies
   - Connection pool limits
   - SSL/TLS for database connections

## Docker Compose Configuration

### Network Definition
```yaml
networks:
  frontend:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/24

  backend:
    driver: bridge
    internal: true  # Critical security feature
    ipam:
      config:
        - subnet: 172.21.0.0/24

  database:
    driver: bridge
    internal: true  # Critical security feature
    ipam:
      config:
        - subnet: 172.22.0.0/24
```

### Service Assignment Example
```yaml
services:
  nginx:
    networks:
      - frontend  # Public access
      - backend   # API access
    ports:
      - "80:80"
      - "443:443"

  api:
    networks:
      - backend   # From nginx
      - database  # To databases
    # NO ports exposed
```

## Deployment Considerations

### Production Checklist

- [ ] Verify `internal: true` on backend and database networks
- [ ] Confirm no database ports exposed
- [ ] Test network isolation with `docker network inspect`
- [ ] Validate firewall rules on host
- [ ] Configure nginx rate limiting
- [ ] Set up SSL certificates
- [ ] Test service discovery between containers
- [ ] Verify no cross-network communication

### Testing Network Isolation

```bash
# Verify network configuration
docker network ls
docker network inspect pazpaz_backend
docker network inspect pazpaz_database

# Test that database is not accessible from host
# This should fail:
telnet localhost 5432  # PostgreSQL
telnet localhost 6379  # Redis
telnet localhost 9000  # MinIO

# Test that API is not accessible from host
# This should fail:
curl http://localhost:8000/health

# Test that only nginx is accessible
# This should work:
curl http://localhost/health
```

### Monitoring

1. **Network Traffic**: Monitor inter-container communication
2. **Connection Pools**: Track database connection usage
3. **Latency**: Measure network latency between services
4. **Security Events**: Log unauthorized connection attempts

## Troubleshooting

### Common Issues

1. **Service Cannot Connect to Database**
   - Verify service is on database network
   - Check service name resolution
   - Validate database credentials

2. **API Not Accessible Through Nginx**
   - Ensure nginx is on backend network
   - Check proxy_pass configuration
   - Verify API health check

3. **Network Isolation Too Restrictive**
   - Review service network assignments
   - Check if service needs database access
   - Validate network definitions

### Debug Commands

```bash
# Check network configuration
docker compose -f docker-compose.prod.yml config

# Inspect running networks
docker network inspect pazpaz_frontend
docker network inspect pazpaz_backend
docker network inspect pazpaz_database

# Test connectivity from container
docker exec pazpaz-nginx ping api
docker exec pazpaz-api ping db

# Check firewall rules (Linux)
sudo iptables -L -n | grep DOCKER
```

## Security Best Practices

1. **Never Expose Database Ports**: Keep all data services internal
2. **Use Strong Network Names**: Avoid default network names
3. **Regular Security Audits**: Test network isolation monthly
4. **Monitor Network Traffic**: Set up alerts for unusual patterns
5. **Document Changes**: Track all network configuration changes
6. **Principle of Least Privilege**: Services only get networks they need
7. **SSL Everywhere**: Use SSL even for internal communications in production

## Compliance

This network architecture supports HIPAA compliance by:

- **Access Control**: Network isolation enforces access boundaries
- **Audit Logging**: All network access can be logged
- **Encryption**: SSL/TLS for all external communications
- **Minimal Attack Surface**: Single entry point reduces vulnerabilities
- **Defense in Depth**: Multiple network layers provide security redundancy

## Future Enhancements

1. **Service Mesh**: Consider Istio/Linkerd for advanced traffic management
2. **Network Policies**: Implement Kubernetes NetworkPolicy for finer control
3. **Zero Trust**: Move to zero-trust networking model
4. **Microsegmentation**: Further segment networks by function
5. **Traffic Encryption**: Implement mTLS for all internal communication