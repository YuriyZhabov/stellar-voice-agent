# Схемы архитектуры и диаграммы системы LiveKit

## Обзор

Данный документ содержит архитектурные диаграммы и схемы системы LiveKit, интегрированной с Voice AI Agent. Диаграммы созданы с использованием Mermaid для наглядного представления компонентов, потоков данных и взаимодействий.

## 1. Общая архитектура системы

```mermaid
graph TB
    subgraph "External Services"
        SIP[SIP Provider<br/>Novofon]
        LKCLOUD[LiveKit Cloud<br/>Server]
    end
    
    subgraph "LiveKit SIP Service"
        LKSIP[LiveKit SIP<br/>Gateway]
        SIPCONFIG[SIP Configuration<br/>livekit-sip-correct.yaml]
    end
    
    subgraph "Voice AI Agent Application"
        subgraph "Authentication Layer"
            AUTH[LiveKit Auth Manager<br/>JWT Tokens]
        end
        
        subgraph "API Layer"
            APICLIENT[LiveKit API Client<br/>Room/Participant Management]
            EGRESS[Egress Service<br/>Recording/Streaming]
            INGRESS[Ingress Service<br/>Media Import]
        end
        
        subgraph "Integration Layer"
            INTEGRATION[Voice AI Integration<br/>Session Management]
            WEBHOOKS[Webhook Handlers<br/>Event Processing]
        end
        
        subgraph "AI Processing"
            STT[Speech-to-Text<br/>Deepgram]
            LLM[Language Model<br/>OpenAI/Groq]
            TTS[Text-to-Speech<br/>Cartesia]
        end
        
        subgraph "Monitoring & Security"
            MONITOR[System Monitor<br/>Health Checks]
            SECURITY[Security Manager<br/>Token Validation]
            ALERTS[Alerting System<br/>Notifications]
        end
    end
    
    subgraph "Storage & Cache"
        REDIS[(Redis<br/>Session Cache)]
        DB[(SQLite<br/>Conversation Logs)]
        FILES[File Storage<br/>Recordings]
    end
    
    %% External connections
    SIP -->|SIP Calls| LKSIP
    LKSIP -->|WebRTC| LKCLOUD
    
    %% Internal connections
    LKSIP -.->|Config| SIPCONFIG
    LKCLOUD -->|Events| WEBHOOKS
    
    %% Authentication flow
    AUTH -->|JWT Tokens| APICLIENT
    AUTH -->|Tokens| LKCLOUD
    
    %% API interactions
    APICLIENT -->|Room API| LKCLOUD
    EGRESS -->|Recording API| LKCLOUD
    INGRESS -->|Import API| LKCLOUD
    
    %% Integration flow
    WEBHOOKS -->|Events| INTEGRATION
    INTEGRATION -->|Audio| STT
    STT -->|Text| LLM
    LLM -->|Response| TTS
    TTS -->|Audio| INTEGRATION
    
    %% Monitoring
    MONITOR -->|Health Checks| APICLIENT
    MONITOR -->|Metrics| ALERTS
    SECURITY -->|Validation| AUTH
    
    %% Storage
    INTEGRATION -->|Sessions| REDIS
    INTEGRATION -->|Logs| DB
    EGRESS -->|Files| FILES
    
    %% Styling
    classDef external fill:#e1f5fe
    classDef livekit fill:#f3e5f5
    classDef api fill:#e8f5e8
    classDef ai fill:#fff3e0
    classDef storage fill:#fce4ec
    
    class SIP,LKCLOUD external
    class LKSIP,SIPCONFIG,AUTH livekit
    class APICLIENT,EGRESS,INGRESS,INTEGRATION,WEBHOOKS api
    class STT,LLM,TTS ai
    class REDIS,DB,FILES storage
```

## 2. Поток аутентификации

```mermaid
sequenceDiagram
    participant App as Voice AI App
    participant Auth as Auth Manager
    participant LK as LiveKit Server
    participant Client as Client SDK
    
    Note over App,Client: JWT Token Creation & Validation
    
    App->>Auth: create_participant_token(identity, room)
    Auth->>Auth: Generate JWT with grants
    Note right of Auth: iss: api_key<br/>sub: identity<br/>exp: +10min<br/>video: grants
    Auth-->>App: JWT Token
    
    App->>Client: Send token to client
    Client->>LK: Connect with JWT token
    LK->>LK: Validate token signature
    LK->>LK: Check token expiration
    LK->>LK: Verify grants for room
    
    alt Token Valid
        LK-->>Client: Connection established
        Client->>LK: Join room
        LK-->>App: Webhook: participant_joined
    else Token Invalid
        LK-->>Client: Authentication failed
        Client-->>App: Connection error
    end
    
    Note over Auth,LK: Auto-refresh every 10 minutes
    loop Every 10 minutes
        Auth->>Auth: Generate new token
        Auth->>Client: Send refreshed token
        Client->>LK: Update connection with new token
    end
```

## 3. SIP интеграция и маршрутизация

```mermaid
flowchart TD
    subgraph "SIP Provider"
        CALLER[Caller<br/>+1234567890]
    end
    
    subgraph "LiveKit SIP Gateway"
        TRUNK[SIP Trunk<br/>novofon-inbound]
        ROUTING[Routing Rules<br/>voice-ai-dispatch]
        DISPATCH[Dispatch Logic]
    end
    
    subgraph "LiveKit Server"
        ROOM[LiveKit Room<br/>voice-ai-call-{id}]
        PARTICIPANT[SIP Participant<br/>caller_+1234567890]
    end
    
    subgraph "Voice AI Agent"
        WEBHOOK[Webhook Handler]
        SESSION[AI Session Manager]
        AIBOT[AI Bot Participant]
    end
    
    %% Call flow
    CALLER -->|1. Incoming Call| TRUNK
    TRUNK -->|2. Match Number| ROUTING
    ROUTING -->|3. Apply Rules| DISPATCH
    DISPATCH -->|4. Create Room| ROOM
    ROOM -->|5. Add Participant| PARTICIPANT
    
    %% Webhook flow
    ROOM -.->|6. room_started| WEBHOOK
    PARTICIPANT -.->|7. participant_joined| WEBHOOK
    WEBHOOK -->|8. Create Session| SESSION
    SESSION -->|9. Join as AI Bot| AIBOT
    AIBOT -->|10. Connect to Room| ROOM
    
    %% Configuration details
    TRUNK -.->|Config| TRUNKCONFIG[numbers: ${SIP_NUMBER}<br/>allowed_addresses: 0.0.0.0/0<br/>auth_required: false]
    ROUTING -.->|Config| ROUTECONFIG[match: to=${SIP_NUMBER}<br/>action: livekit_room<br/>template: voice-ai-call-{call_id}]
    
    %% Styling
    classDef sip fill:#e3f2fd
    classDef livekit fill:#f1f8e9
    classDef ai fill:#fff8e1
    classDef config fill:#fce4ec
    
    class CALLER,TRUNK sip
    class ROUTING,DISPATCH,ROOM,PARTICIPANT livekit
    class WEBHOOK,SESSION,AIBOT ai
    class TRUNKCONFIG,ROUTECONFIG config
```

## 4. Voice AI обработка аудио

```mermaid
sequenceDiagram
    participant Caller as SIP Caller
    participant Room as LiveKit Room
    participant AI as AI Bot
    participant STT as Speech-to-Text
    participant LLM as Language Model
    participant TTS as Text-to-Speech
    participant Session as Session Manager
    
    Note over Caller,Session: Real-time Audio Processing Pipeline
    
    Caller->>Room: Audio stream (RTP)
    Room->>AI: Audio track data
    AI->>STT: Raw audio bytes
    STT->>STT: Process speech
    STT-->>AI: Transcribed text
    
    AI->>Session: Update conversation state
    AI->>LLM: Send user message + context
    LLM->>LLM: Generate response
    LLM-->>AI: AI response text
    
    AI->>TTS: Synthesize speech
    TTS->>TTS: Generate audio
    TTS-->>AI: Audio bytes
    
    AI->>Room: Publish audio track
    Room->>Caller: Audio stream (RTP)
    
    Note over AI,Session: Parallel processing
    par
        AI->>Session: Log conversation
    and
        AI->>Session: Update metrics
    and
        AI->>Session: Check conversation state
    end
    
    alt Conversation continues
        Note over Caller,Session: Loop for next audio chunk
    else Call ends
        Caller->>Room: Disconnect
        Room-->>AI: participant_left event
        AI->>Session: End session & cleanup
    end
```

## 5. Мониторинг и health checks

```mermaid
graph TB
    subgraph "Monitoring System"
        MONITOR[System Monitor]
        HEALTH[Health Checker]
        METRICS[Metrics Collector]
        ALERTS[Alert Manager]
    end
    
    subgraph "Health Check Targets"
        subgraph "LiveKit Services"
            ROOMAPI[Room Service API]
            EGRESSAPI[Egress API]
            INGRESSAPI[Ingress API]
            SIPAPI[SIP API]
        end
        
        subgraph "External Services"
            LKSERVER[LiveKit Server]
            REDIS[Redis Cache]
            SIPGW[SIP Gateway]
        end
        
        subgraph "AI Services"
            STTSERVICE[STT Service]
            LLMSERVICE[LLM Service]
            TTSSERVICE[TTS Service]
        end
    end
    
    subgraph "Monitoring Outputs"
        DASHBOARD[Grafana Dashboard]
        LOGS[Structured Logs]
        WEBHOOKS[Alert Webhooks]
        PROMETHEUS[Prometheus Metrics]
    end
    
    %% Health check flows
    MONITOR -->|Check every 60s| HEALTH
    HEALTH -->|Test endpoints| ROOMAPI
    HEALTH -->|Test endpoints| EGRESSAPI
    HEALTH -->|Test endpoints| INGRESSAPI
    HEALTH -->|Test endpoints| SIPAPI
    
    HEALTH -->|Ping/Connect| LKSERVER
    HEALTH -->|Redis PING| REDIS
    HEALTH -->|SIP OPTIONS| SIPGW
    
    HEALTH -->|API calls| STTSERVICE
    HEALTH -->|API calls| LLMSERVICE
    HEALTH -->|API calls| TTSSERVICE
    
    %% Metrics collection
    MONITOR -->|Collect metrics| METRICS
    METRICS -->|Performance data| PROMETHEUS
    METRICS -->|System stats| DASHBOARD
    
    %% Alerting
    HEALTH -->|Status changes| ALERTS
    METRICS -->|Threshold breaches| ALERTS
    ALERTS -->|Notifications| WEBHOOKS
    ALERTS -->|Log events| LOGS
    
    %% Health status indicators
    ROOMAPI -.->|✓ Healthy<br/>⚠ Degraded<br/>✗ Unhealthy| HEALTHSTATUS[Health Status]
    EGRESSAPI -.->|Latency: <100ms<br/>Success: >99%| HEALTHSTATUS
    INGRESSAPI -.->|Connections: Active<br/>Errors: <1%| HEALTHSTATUS
    
    %% Styling
    classDef monitor fill:#e8f5e8
    classDef service fill:#e3f2fd
    classDef external fill:#fff3e0
    classDef output fill:#f3e5f5
    
    class MONITOR,HEALTH,METRICS,ALERTS monitor
    class ROOMAPI,EGRESSAPI,INGRESSAPI,SIPAPI service
    class LKSERVER,REDIS,SIPGW,STTSERVICE,LLMSERVICE,TTSSERVICE external
    class DASHBOARD,LOGS,WEBHOOKS,PROMETHEUS output
```

## 6. Безопасность и управление токенами

```mermaid
stateDiagram-v2
    [*] --> TokenCreation
    
    state TokenCreation {
        [*] --> GenerateJWT
        GenerateJWT --> SetClaims
        SetClaims --> SignToken
        SignToken --> [*]
        
        state SetClaims {
            [*] --> SetIssuer
            SetIssuer --> SetSubject
            SetSubject --> SetExpiration
            SetExpiration --> SetGrants
            SetGrants --> [*]
        }
    }
    
    TokenCreation --> TokenValidation
    
    state TokenValidation {
        [*] --> CheckSignature
        CheckSignature --> CheckExpiration
        CheckExpiration --> CheckGrants
        CheckGrants --> [*]
        
        CheckSignature --> InvalidSignature : Invalid
        CheckExpiration --> TokenExpired : Expired
        CheckGrants --> InsufficientGrants : No permissions
        
        InvalidSignature --> [*]
        TokenExpired --> TokenRefresh
        InsufficientGrants --> [*]
    }
    
    TokenValidation --> ActiveToken : Valid
    
    state ActiveToken {
        [*] --> InUse
        InUse --> AutoRefresh : Every 10 min
        AutoRefresh --> InUse
        InUse --> ManualRevoke : Admin action
        ManualRevoke --> [*]
    }
    
    state TokenRefresh {
        [*] --> GenerateNew
        GenerateNew --> InvalidateOld
        InvalidateOld --> UpdateClient
        UpdateClient --> [*]
    }
    
    TokenRefresh --> ActiveToken
    ActiveToken --> [*] : Expired/Revoked
    
    note right of TokenCreation
        JWT Claims:
        - iss: API_KEY
        - sub: participant_identity
        - iat: current_time
        - exp: current_time + 10min
        - video: VideoGrants
    end note
    
    note right of TokenValidation
        Security Checks:
        - HMAC-SHA256 signature
        - Expiration time
        - Required grants
        - Room permissions
    end note
```

## 7. Egress и Ingress потоки данных

```mermaid
flowchart LR
    subgraph "Input Sources"
        ROOM[LiveKit Room<br/>Audio/Video Tracks]
        RTMPSTREAM[RTMP Stream<br/>OBS/XSplit]
        URLSOURCE[URL Source<br/>HLS/MP4/MOV]
        WHIPSOURCE[WHIP Source<br/>WebRTC Browser]
    end
    
    subgraph "LiveKit Processing"
        subgraph "Ingress Processing"
            RTMPINGRESS[RTMP Ingress]
            URLINGRESS[URL Ingress]
            WHIPINGRESS[WHIP Ingress]
        end
        
        LKROOM[LiveKit Room<br/>Media Processing]
        
        subgraph "Egress Processing"
            ROOMEGRESS[Room Composite<br/>Egress]
            TRACKEGRESS[Track Composite<br/>Egress]
            WEBEGRESS[Web Egress<br/>Browser Recording]
        end
    end
    
    subgraph "Output Destinations"
        subgraph "File Outputs"
            MP4[MP4 Files]
            OGG[OGG Files]
            WEBM[WebM Files]
        end
        
        subgraph "Streaming Outputs"
            RTMPOUT[RTMP Streams<br/>Twitch/YouTube]
            HLS[HLS Streams]
            DASH[DASH Streams]
        end
        
        subgraph "Cloud Storage"
            S3[AWS S3]
            AZURE[Azure Blob]
            GCS[Google Cloud Storage]
        end
    end
    
    %% Ingress flows
    RTMPSTREAM -->|Ingest| RTMPINGRESS
    URLSOURCE -->|Import| URLINGRESS
    WHIPSOURCE -->|WebRTC| WHIPINGRESS
    
    RTMPINGRESS -->|Publish tracks| LKROOM
    URLINGRESS -->|Publish tracks| LKROOM
    WHIPINGRESS -->|Publish tracks| LKROOM
    
    %% Room processing
    ROOM -->|Live tracks| LKROOM
    
    %% Egress flows
    LKROOM -->|All tracks| ROOMEGRESS
    LKROOM -->|Selected tracks| TRACKEGRESS
    LKROOM -->|Browser capture| WEBEGRESS
    
    %% Output routing
    ROOMEGRESS -->|Record| MP4
    ROOMEGRESS -->|Record| OGG
    ROOMEGRESS -->|Stream| RTMPOUT
    ROOMEGRESS -->|Stream| HLS
    
    TRACKEGRESS -->|Sync A/V| WEBM
    TRACKEGRESS -->|Upload| S3
    TRACKEGRESS -->|Upload| AZURE
    
    WEBEGRESS -->|Capture| MP4
    WEBEGRESS -->|Upload| GCS
    WEBEGRESS -->|Stream| DASH
    
    %% Configuration examples
    RTMPINGRESS -.->|Config| RTMPCONFIG[name: obs-stream<br/>room: streaming-room<br/>participant: streamer]
    ROOMEGRESS -.->|Config| EGRESSCONFIG[layout: grid<br/>audio_only: false<br/>video_only: false]
    
    %% Styling
    classDef input fill:#e8f5e8
    classDef processing fill:#e3f2fd
    classDef output fill:#fff3e0
    classDef storage fill:#f3e5f5
    
    class ROOM,RTMPSTREAM,URLSOURCE,WHIPSOURCE input
    class RTMPINGRESS,URLINGRESS,WHIPINGRESS,LKROOM,ROOMEGRESS,TRACKEGRESS,WEBEGRESS processing
    class MP4,OGG,WEBM,RTMPOUT,HLS,DASH output
    class S3,AZURE,GCS storage
```

## 8. Обработка ошибок и восстановление

```mermaid
flowchart TD
    START[System Start] --> INIT[Initialize Components]
    
    INIT --> HEALTHCHECK{Health Check}
    HEALTHCHECK -->|Pass| RUNNING[System Running]
    HEALTHCHECK -->|Fail| DIAGNOSE[Run Diagnostics]
    
    RUNNING --> MONITOR[Monitor Operations]
    MONITOR --> ERROR{Error Detected?}
    ERROR -->|No| MONITOR
    ERROR -->|Yes| CLASSIFY[Classify Error]
    
    CLASSIFY --> AUTHERROR{Auth Error?}
    CLASSIFY --> APIERROR{API Error?}
    CLASSIFY --> SIPERROR{SIP Error?}
    CLASSIFY --> NETWORKERROR{Network Error?}
    
    %% Authentication errors
    AUTHERROR -->|Yes| REFRESHTOKEN[Refresh JWT Token]
    REFRESHTOKEN --> RETRYAUTH[Retry Operation]
    RETRYAUTH --> SUCCESS{Success?}
    SUCCESS -->|Yes| RUNNING
    SUCCESS -->|No| ESCALATE[Escalate to Admin]
    
    %% API errors
    APIERROR -->|Yes| CHECKAPI[Check API Status]
    CHECKAPI --> RETRYAPI[Retry with Backoff]
    RETRYAPI --> APISUCCESS{Success?}
    APISUCCESS -->|Yes| RUNNING
    APISUCCESS -->|No| FALLBACK[Use Fallback API]
    FALLBACK --> RUNNING
    
    %% SIP errors
    SIPERROR -->|Yes| CHECKSIP[Check SIP Config]
    CHECKSIP --> RELOADSIP[Reload SIP Config]
    RELOADSIP --> TESTSIP[Test SIP Connection]
    TESTSIP --> SIPSUCCESS{Success?}
    SIPSUCCESS -->|Yes| RUNNING
    SIPSUCCESS -->|No| SIPFALLBACK[Use Backup Config]
    SIPFALLBACK --> RUNNING
    
    %% Network errors
    NETWORKERROR -->|Yes| CHECKNET[Check Network]
    CHECKNET --> RECONNECT[Attempt Reconnect]
    RECONNECT --> NETSUCCESS{Success?}
    NETSUCCESS -->|Yes| RUNNING
    NETSUCCESS -->|No| WAITRETRY[Wait & Retry]
    WAITRETRY --> RECONNECT
    
    %% Diagnostics and recovery
    DIAGNOSE --> LOGISSUE[Log Issue Details]
    LOGISSUE --> AUTOFIX[Attempt Auto-fix]
    AUTOFIX --> FIXSUCCESS{Fixed?}
    FIXSUCCESS -->|Yes| RUNNING
    FIXSUCCESS -->|No| MANUALFIX[Require Manual Fix]
    
    %% Escalation
    ESCALATE --> ALERT[Send Alert]
    ALERT --> MANUALFIX
    MANUALFIX --> ADMINACTION[Admin Action Required]
    ADMINACTION --> RUNNING
    
    %% Emergency procedures
    MANUALFIX --> EMERGENCY{Critical System?}
    EMERGENCY -->|Yes| FAILSAFE[Activate Failsafe]
    EMERGENCY -->|No| DEGRADED[Degraded Mode]
    
    FAILSAFE --> BACKUP[Switch to Backup]
    BACKUP --> RUNNING
    
    DEGRADED --> LIMITEDOPS[Limited Operations]
    LIMITEDOPS --> RUNNING
    
    %% Styling
    classDef normal fill:#e8f5e8
    classDef error fill:#ffebee
    classDef recovery fill:#e3f2fd
    classDef critical fill:#fff3e0
    
    class START,INIT,RUNNING,MONITOR normal
    class ERROR,CLASSIFY,AUTHERROR,APIERROR,SIPERROR,NETWORKERROR error
    class REFRESHTOKEN,RETRYAUTH,CHECKAPI,RETRYAPI,CHECKSIP,RELOADSIP recovery
    class EMERGENCY,FAILSAFE,ESCALATE,ALERT critical
```

## 9. Производительность и масштабирование

```mermaid
graph TB
    subgraph "Load Balancing"
        LB[Load Balancer]
        LB --> APP1[App Instance 1]
        LB --> APP2[App Instance 2]
        LB --> APP3[App Instance N]
    end
    
    subgraph "Connection Pooling"
        APP1 --> POOL1[Connection Pool 1<br/>Max: 100 connections]
        APP2 --> POOL2[Connection Pool 2<br/>Max: 100 connections]
        APP3 --> POOL3[Connection Pool N<br/>Max: 100 connections]
    end
    
    subgraph "LiveKit Infrastructure"
        POOL1 --> LKAPI[LiveKit API<br/>Rate Limited]
        POOL2 --> LKAPI
        POOL3 --> LKAPI
        
        LKAPI --> LKSERVER1[LiveKit Server 1]
        LKAPI --> LKSERVER2[LiveKit Server 2]
        LKAPI --> LKSERVERN[LiveKit Server N]
    end
    
    subgraph "Caching Layer"
        REDIS1[(Redis Primary)]
        REDIS2[(Redis Replica)]
        REDIS3[(Redis Replica)]
        
        REDIS1 --> REDIS2
        REDIS1 --> REDIS3
    end
    
    subgraph "Performance Monitoring"
        METRICS[Metrics Collection]
        METRICS --> LATENCY[API Latency<br/>Target: <100ms]
        METRICS --> THROUGHPUT[Throughput<br/>Target: 1000 req/s]
        METRICS --> ERRORS[Error Rate<br/>Target: <1%]
        METRICS --> RESOURCES[Resource Usage<br/>CPU: <80%, RAM: <80%]
    end
    
    subgraph "Auto-scaling Triggers"
        TRIGGER1[CPU > 80%] --> SCALEUP[Scale Up]
        TRIGGER2[Memory > 80%] --> SCALEUP
        TRIGGER3[Queue Length > 100] --> SCALEUP
        TRIGGER4[Response Time > 200ms] --> SCALEUP
        
        SCALEDOWN[Scale Down] --> TRIGGER5[CPU < 30%]
        SCALEDOWN --> TRIGGER6[Memory < 30%]
        SCALEDOWN --> TRIGGER7[Queue Length < 10]
    end
    
    %% Performance optimizations
    APP1 -.->|Session Cache| REDIS1
    APP2 -.->|Session Cache| REDIS2
    APP3 -.->|Session Cache| REDIS3
    
    %% Monitoring connections
    APP1 -.->|Metrics| METRICS
    APP2 -.->|Metrics| METRICS
    APP3 -.->|Metrics| METRICS
    
    %% Scaling actions
    SCALEUP -.->|Add Instance| LB
    SCALEDOWN -.->|Remove Instance| LB
    
    %% Performance targets
    LATENCY -.->|Alert if >100ms| ALERT1[Latency Alert]
    THROUGHPUT -.->|Alert if <500 req/s| ALERT2[Throughput Alert]
    ERRORS -.->|Alert if >1%| ALERT3[Error Rate Alert]
    RESOURCES -.->|Alert if >80%| ALERT4[Resource Alert]
    
    %% Styling
    classDef app fill:#e8f5e8
    classDef infra fill:#e3f2fd
    classDef cache fill:#fff3e0
    classDef monitor fill:#f3e5f5
    classDef alert fill:#ffebee
    
    class APP1,APP2,APP3,POOL1,POOL2,POOL3 app
    class LB,LKAPI,LKSERVER1,LKSERVER2,LKSERVERN infra
    class REDIS1,REDIS2,REDIS3 cache
    class METRICS,LATENCY,THROUGHPUT,ERRORS,RESOURCES monitor
    class ALERT1,ALERT2,ALERT3,ALERT4 alert
```

## 10. Развертывание и CI/CD

```mermaid
gitgraph
    commit id: "Initial Setup"
    branch development
    checkout development
    commit id: "Add Auth Manager"
    commit id: "Add API Client"
    commit id: "Add SIP Config"
    
    branch feature/monitoring
    checkout feature/monitoring
    commit id: "Add Health Checks"
    commit id: "Add Metrics"
    commit id: "Add Alerting"
    
    checkout development
    merge feature/monitoring
    commit id: "Integration Tests"
    
    branch feature/security
    checkout feature/security
    commit id: "Add Token Validation"
    commit id: "Add Security Audit"
    
    checkout development
    merge feature/security
    commit id: "Security Tests"
    
    checkout main
    merge development
    commit id: "Release v1.0.0"
    
    branch hotfix/auth-fix
    checkout hotfix/auth-fix
    commit id: "Fix Token Refresh"
    
    checkout main
    merge hotfix/auth-fix
    commit id: "Release v1.0.1"
    
    checkout development
    merge main
    commit id: "Sync with main"
```

### CI/CD Pipeline

```mermaid
flowchart LR
    subgraph "Source Control"
        GIT[Git Repository]
        PR[Pull Request]
    end
    
    subgraph "CI Pipeline"
        LINT[Code Linting<br/>flake8, black]
        TEST[Unit Tests<br/>pytest]
        INTEGRATION[Integration Tests<br/>LiveKit API]
        SECURITY[Security Scan<br/>bandit, safety]
        BUILD[Build Docker Image]
    end
    
    subgraph "CD Pipeline"
        STAGING[Deploy to Staging]
        E2E[E2E Tests]
        APPROVAL[Manual Approval]
        PRODUCTION[Deploy to Production]
    end
    
    subgraph "Monitoring"
        HEALTHCHECK[Health Check]
        ROLLBACK[Auto Rollback]
        METRICS[Deployment Metrics]
    end
    
    %% CI flow
    GIT --> PR
    PR --> LINT
    LINT --> TEST
    TEST --> INTEGRATION
    INTEGRATION --> SECURITY
    SECURITY --> BUILD
    
    %% CD flow
    BUILD --> STAGING
    STAGING --> E2E
    E2E --> APPROVAL
    APPROVAL --> PRODUCTION
    
    %% Monitoring flow
    PRODUCTION --> HEALTHCHECK
    HEALTHCHECK -->|Fail| ROLLBACK
    HEALTHCHECK -->|Pass| METRICS
    ROLLBACK --> STAGING
    
    %% Quality gates
    LINT -.->|Fail| FAIL1[❌ Pipeline Failed]
    TEST -.->|Fail| FAIL2[❌ Pipeline Failed]
    INTEGRATION -.->|Fail| FAIL3[❌ Pipeline Failed]
    SECURITY -.->|Fail| FAIL4[❌ Pipeline Failed]
    E2E -.->|Fail| FAIL5[❌ Deployment Failed]
    
    %% Styling
    classDef source fill:#e8f5e8
    classDef ci fill:#e3f2fd
    classDef cd fill:#fff3e0
    classDef monitor fill:#f3e5f5
    classDef fail fill:#ffebee
    
    class GIT,PR source
    class LINT,TEST,INTEGRATION,SECURITY,BUILD ci
    class STAGING,E2E,APPROVAL,PRODUCTION cd
    class HEALTHCHECK,ROLLBACK,METRICS monitor
    class FAIL1,FAIL2,FAIL3,FAIL4,FAIL5 fail
```

## Заключение

Данные диаграммы и схемы предоставляют полное представление об архитектуре системы LiveKit, интегрированной с Voice AI Agent. Они помогают понять:

1. **Общую архитектуру** - как компоненты взаимодействуют друг с другом
2. **Потоки данных** - как информация перемещается через систему
3. **Безопасность** - как обеспечивается защита и аутентификация
4. **Производительность** - как система масштабируется и оптимизируется
5. **Мониторинг** - как отслеживается состояние системы
6. **Развертывание** - как система разворачивается и обновляется

Используйте эти диаграммы для:
- Понимания архитектуры системы
- Планирования изменений и улучшений
- Обучения новых разработчиков
- Документирования решений по дизайну
- Troubleshooting проблем

Все диаграммы созданы в формате Mermaid и могут быть легко обновлены и модифицированы по мере развития системы.