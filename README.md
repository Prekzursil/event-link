# Event Link

A full-stack application with Angular frontend and FastAPI backend.

## Project Structure

```
event-link/
├── ui/                 # Angular frontend application
├── backend/           # FastAPI backend application
├── .gitignore        # Git ignore file
└── README.md         # This file
```

## Prerequisites

- **Node.js**: Version 20.18.1 or higher
- **npm**: Comes with Node.js
- **Python**: Version 3.11 or higher
- **uv**: Python package manager (install with `pip install uv` or `brew install uv`)

## Installation

### Backend Setup (FastAPI)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies using uv:
   ```bash
   uv sync
   ```

3. Activate the virtual environment:
   ```bash
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\Scripts\activate     # On Windows
   ```

### Frontend Setup (Angular)

1. Navigate to the UI directory:
   ```bash
   cd ui
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

## Running the Application

### Start the Backend (FastAPI)

From the `backend` directory:

```bash
# Option 1: Using uv
uv run uvicorn app.api:app --reload --host 0.0.0.0 --port 8000

# Option 2: After activating virtual environment
uvicorn app.api:app --reload --host 0.0.0.0 --port 8000

# Option 3: Using Python directly
python main.py
```

The backend will be available at: http://localhost:8000

- API Documentation (Swagger): http://localhost:8000/docs
- Alternative API Documentation (ReDoc): http://localhost:8000/redoc

### Start the Frontend (Angular)

From the `ui` directory:

```bash
npm start
# or
ng serve
```

The frontend will be available at: http://localhost:4200

## Development

### Backend Development

The FastAPI backend includes:
- CORS middleware configured for Angular development server
- Health check endpoint at `/api/health`
- Auto-reloading with `--reload` flag
- Interactive API documentation

### Frontend Development

The Angular application includes:
- Angular Material UI components
- SCSS styling
- Routing enabled
- Development server with hot reload

### Making Changes

1. **Backend**: The FastAPI server will automatically reload when you make changes to Python files
2. **Frontend**: The Angular development server will automatically reload when you make changes to TypeScript/HTML/SCSS files

## API Endpoints

- `GET /` - Welcome message
- `GET /api/health` - Health check
- `GET /api/events` - Get events (placeholder)

## Technologies Used

### Frontend
- **Angular 18** - Frontend framework
- **Angular Material** - UI component library
- **SCSS** - Styling
- **TypeScript** - Programming language

### Backend
- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation
- **Python 3.11+** - Programming language

## Next Steps

1. Implement authentication system
2. Add database integration (PostgreSQL/SQLite)
3. Create event management features
4. Add user management
5. Implement real-time features with WebSockets
6. Add testing (Jest for Angular, pytest for FastAPI)
7. Set up CI/CD pipeline

## Troubleshooting

### Common Issues

1. **Port already in use**: Change the port in the run commands
2. **Node.js version issues**: Update Node.js to the latest LTS version
3. **Python version issues**: Ensure Python 3.11+ is installed
4. **uv not found**: Install uv using `pip install uv` or `brew install uv`

### Logs

- Backend logs will appear in the terminal where you started the FastAPI server
- Frontend logs will appear in the browser console and terminal where you started the Angular dev server