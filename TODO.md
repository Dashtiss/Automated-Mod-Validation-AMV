# AMV Development Checklist

## Phase Status Overview

- [x] Phase 1 - Alpha: Core Setup & Basic Connections
- [x] Phase 2 - Beta: Test Automation
- [ ] Phase 3 - Release Candidate
- [ ] Phase 4 - Future Improvements

## Detailed Feature Checklist

### Core Features

| Feature | Status | Phase | Notes |
|---------|--------|-------|-------|
| Basic Configuration System | [x] | Alpha 1 | Settings.py implemented |
| Logging System | [x] | Alpha 1 | JSON formatting, multiple handlers |
| Error Handling | [x] | Alpha 1 | Comprehensive with retries |
| Core Engine | [x] | Alpha 1 | AsyncIO-based orchestration |
| API Endpoints | [x] | Alpha 1 | FastAPI implementation |

### Server Management

| Feature | Status | Phase | Notes |
|---------|--------|-------|-------|
| Pterodactyl Integration | [x] | Alpha 2 | Full server lifecycle management |
| Server Deployment | [x] | Alpha 2 | Automated setup and cleanup |
| Mod File Management | [x] | Alpha 2 | Upload, cleanup, version tracking |
| Proxmox VM Integration | [-] | Alpha 2 | Currently disabled |
| SSH Command Execution | [ ] | Alpha 2 | Replaced by Pterodactyl API |

### Mod Management

| Feature | Status | Phase | Notes |
|---------|--------|-------|-------|
| Version Tracking | [x] | Beta 1 | Modrinth API integration |
| Loader Selection | [x] | Beta 1 | Support for Fabric/Forge/NeoForge |
| Version Compatibility | [x] | Beta 1 | Smart version matching |
| Mod Testing | [-] | Beta 1 | Basic implementation |
| Auto-Installation | [x] | Beta 1 | Server-side complete |

### Testing & Automation

| Feature | Status | Phase | Notes |
|---------|--------|-------|-------|
| Test Execution | [-] | Beta 2 | In progress |
| Log Collection | [x] | Beta 2 | Comprehensive logging |
| Crash Detection | [ ] | Beta 2 | Planned |
| Performance Metrics | [ ] | Beta 2 | Planned |
| Client Automation | [ ] | Beta 2 | Not started |

### Discord Integration

| Feature | Status | Phase | Notes |
|---------|--------|-------|-------|
| Status Updates | [x] | Alpha 1 | Real-time with embeds |
| Command Handling | [x] | Alpha 1 | Basic controls implemented |
| Error Reporting | [x] | Alpha 1 | Automatic notifications |
| Test Notifications | [x] | Beta 1 | Status tracking |

### Web Interface

| Feature | Status | Phase | Notes |
|---------|--------|-------|-------|
| Basic Dashboard | [ ] | RC 1 | Planned |
| Status Monitoring | [ ] | RC 1 | Planned |
| Test Results Display | [ ] | RC 1 | Planned |
| Configuration UI | [ ] | RC 1 | Planned |

### Documentation

| Feature | Status | Phase | Notes |
|---------|--------|-------|-------|
| API Documentation | [-] | RC 1 | In progress |
| Setup Guide | [-] | RC 1 | Basic version complete |
| User Guide | [ ] | RC 1 | Not started |
| Developer Guide | [ ] | RC 1 | Not started |

### Future Improvements

| Feature | Priority | Notes |
|---------|----------|-------|
| Scheduled Testing | Medium | Automated test scheduling |
| Advanced Automation | High | Enhanced test scenarios |
| Performance Monitoring | Medium | Detailed metrics collection |
| Multi-Client Testing | Low | Multiple client instances |
| Container Orchestration | Low | For scaled testing |

## Legend

- [x] Complete
- [-] In Progress
- [ ] Not Started