# EVIDENS — Contexto para desarrollo asistido por IA

## Qué es este proyecto
Sistema de recopilación y organización de evidencias de exámenes prácticos
en la asignatura de Redes de Computadoras I de la UCB "San Pablo" Cochabamba.
Proyecto de titulación de Ingeniería de Sistemas — desarrollador único.

## Estado actual del repositorio
- Frontend Angular 19 inicializado en /frontend (ng new, standalone, CSS puro, sin SSR)
- Backend FastAPI: carpeta /backend/app creada, sin código aún
- Cliente portable: carpeta /agent creada, sin código aún
- Base de datos: PostgreSQL 16 en Neon (serverless, desarrollo)
- Variables de entorno: /backend/.env (no está en git, ver DATABASE_URL abajo)

## Estructura de carpetas
titulacion/
├── backend/
│   └── app/
│       ├── core/         ← config.py, database.py, security.py
│       ├── models/       ← tablas SQLAlchemy (un archivo por entidad)
│       ├── schemas/      ← Pydantic (request/response)
│       ├── repositories/ ← acceso a datos (queries)
│       ├── services/     ← lógica de negocio
│       ├── routers/      ← endpoints HTTP y WebSocket
│       └── main.py       ← entrada FastAPI
├── frontend/             ← Angular 19
│   └── src/app/
│       ├── core/         ← interceptors, guards, services singleton
│       ├── features/     ← un módulo por OE (auth, exam, monitor, evidence)
│       └── shared/       ← componentes y pipes reutilizables
└── agent/                ← cliente portable Python
    ├── core/             ← config, comunicación con servidor
    ├── capture/          ← keylogger, buffer de video, detector de intención
    ├── control/          ← firewall (hosts), monitoreo USB
    ├── ui/               ← pantallas Tkinter (PIN, VLSM, instrucciones)
    └── main.py           ← entrada del cliente portable

## Stack tecnológico exacto
- Python 3.12 — backend y cliente portable
- FastAPI 0.142 — backend web framework
- SQLAlchemy 2.1 async — ORM
- Alembic 1.20 — migraciones
- PostgreSQL 16 — base de datos
- Angular 19 standalone — frontend
- TypeScript — obligatorio, sin JS puro
- CSS puro — sin Tailwind, sin Bootstrap, sin SCSS
- PyInstaller — empaquetado del cliente portable
- pynput — hooks de teclado
- mss — captura de pantalla
- wmi — monitoreo USB

## Arquitectura
- Despliegue: SBA distribuida (3 artefactos independientes)
- Interna backend: capas (router → service → repository → model)
- Comunicación: REST para operaciones, WebSocket para monitoreo en tiempo real
- La lógica de negocio NUNCA va en routers ni en modelos — siempre en services

## Modelo de datos (tablas principales)
institutions (id, name, country)
subjects (id, institution_id, name, code)
users (id, institution_id, email, hashed_password, role, name)
  roles: 'admin' | 'teacher' | 'student'
courses (id, subject_id, teacher_id, semester, parallel)
enrollments (id, course_id, student_id)
exam_sessions (id, course_id, type, started_at, ended_at, firewall_profile, config JSONB)
  types: 'parcial_1' | 'parcial_2' | 'recuperatorio' | 'final'
exam_tokens (id, session_id, student_id, token VARCHAR(10), station_mac, vlsm_group, enabled_at)
evidence_packages (id, token_id, uploaded_at, keylog JSONB, pkt_file_path, clips JSONB)
firewall_profiles (id, name, blocked_domains JSONB)

## Convenciones de código

### Python / Backend
- snake_case para variables, funciones y archivos
- PascalCase para clases
- Async/await en todo el backend — nunca funciones síncronas en routers o services
- Nombres de dominio en español: sesion_examen, estudiante, evidencia
- Nombres de infraestructura en inglés: router, service, repository, model
- Cada archivo de modelo = una entidad
- Cada router tiene su propio archivo en /routers/
- Los repositories devuelven modelos SQLAlchemy
- Los services reciben y devuelven schemas Pydantic

### Angular / Frontend
- Componentes standalone siempre — nunca NgModules
- Signals para estado reactivo — nunca BehaviorSubject para estado local
- Un componente por archivo
- Nombres en kebab-case para archivos: exam-monitor.component.ts
- PascalCase para clases: ExamMonitorComponent
- Servicios singleton en /core/services/
- Interfaces TypeScript para todos los modelos — nunca "any"

### General
- Nunca hardcodear URLs, credenciales o configuración — siempre environment.ts o .env
- Nunca lógica de negocio en componentes Angular — va en services
- Comentarios solo cuando el código no se explica solo
- Un archivo no debe superar 200 líneas — dividir si crece más

## Variables de entorno backend (.env)
DATABASE_URL=postgresql+asyncpg://neondb_owner:npg_kAb2OS5qomuh@ep-snowy-boat-b8x3fvcm-pooler.c-14.us-east-1.aws.neon.tech/neondb?ssl=require
SECRET_KEY=cambiar_por_clave_segura_en_produccion
ENVIRONMENT=development
APP_NAME=EVIDENS

NOTA: la URL original de Neon usa el prefijo "postgresql://" y el parámetro
"channel_binding=require" — para usarla con SQLAlchemy async hay que cambiar
el prefijo a "postgresql+asyncpg://" y quitar "channel_binding" porque asyncpg
no lo soporta como query param (el SSL ya queda cubierto con "ssl=require").

## Variables de entorno frontend (environment.ts)
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000',
  wsUrl: 'ws://localhost:8000'
};

## Lo que NO hace el sistema
- No califica automáticamente — calificación manual exclusiva del docente
- No bloquea todo el internet — aplica firewall selectivo por dominios
- No soporta Linux ni macOS en el cliente portable (solo Windows)
- No usa Scrum — metodología XP adaptada a desarrollador individual

## Flujo del examen (resumen para contexto de código)
1. Docente crea sesión → genera tokens individuales por estudiante
2. Estudiante abre cliente portable → ingresa token → ve requerimientos VLSM
3. Docente valida subneteo manualmente → habilita estación desde panel web
4. Cliente recibe habilitación → muestra instrucciones → aplica firewall → inicia captura
5. Cliente corre cronómetro local (no depende del servidor para temporización)
6. Al vencer el tiempo → empaqueta evidencia → transfiere por LAN → espera confirmación
7. Docente revisa evidencia organizada: sesión → estudiante → dispositivo de red

## Cómo pedirme código
Siempre especificá:
- En qué archivo exacto va el código
- Si es nuevo archivo o modificación de uno existente
- Qué dependencias puede importar (solo las del stack definido arriba)
- Si necesita test unitario

## Orden de desarrollo (por OE)
1. OE1: Arquitectura — models + database.py + alembic init + primera migración
2. OE2: Gestión de usuarios — auth (JWT), CRUD usuarios, gestión de exámenes, tokens
3. OE3: Cliente portable — keylogger + buffer + detector + firewall + UI Tkinter
4. OE4: Panel de monitoreo — WebSocket, heartbeat, alertas en tiempo real
5. OE5: Clasificador — segmentación por hostname, estructura jerárquica, interfaz revisión
6. OE6: Pruebas — integración, funcionales, entorno controlado