# ⛳ Stableford Tournament App

App en Streamlit para gestionar torneos de golf formato Stableford, con Supabase como base de datos.

## Features

- **Leaderboard público** — ranking en tiempo real con puntos Stableford
- **Admin panel** — crear torneos, asignar jugadores/guests, capturar scores hoyo por hoyo
- **Sesión persistente** — no pierde el login al bloquear el celular
- **Hándicap automático** — calcula Course Handicap y golpes de ventaja por hoyo

## Setup

### 1. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 2. Configurar credenciales
Edita `.streamlit/secrets.toml`:
```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "your-anon-key"
ADMIN_PIN = "tu-pin-seguro"
```

### 3. Correr
```bash
streamlit run app.py
```

## Estructura
```
├── app.py              # App principal
├── db.py               # Helpers de Supabase
├── stableford.py       # Lógica de puntos Stableford
├── requirements.txt
└── .streamlit/
    └── secrets.toml    # Credenciales (NO subir a git)
```

## Puntos Stableford

| Net vs Par | Puntos |
|-----------|--------|
| Eagle o mejor | 4 |
| Birdie | 3 |
| Par | 2 |
| Bogey | 1 |
| Doble bogey+ | 0 |
