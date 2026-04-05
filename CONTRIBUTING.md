# Contributing Guide

## Scope
This repository uses a Django backend and React frontend. Keep changes focused, documented, and testable.

## Local Setup
1. Create and activate a virtual environment.
2. Install backend deps with `pip install -r backend/requirements-dev.txt`.
3. Run backend migrations from `backend/` with `python manage.py migrate`.
4. Start backend with `python manage.py runserver 127.0.0.1:8000`.
5. Start frontend from `frontend/` with `npm install` then `npm start`.

## Branch and PR Rules
1. Use short, descriptive branch names.
2. Keep pull requests small and cohesive.
3. Include a clear problem statement and test notes in the PR description.
4. Link related issues when relevant.

## Quality Checklist
1. Backend: `python manage.py check`
2. Backend tests: `pytest`
3. Frontend build: `npm run build`
4. Update docs for API, env vars, and behavior changes.

## Coding Guidelines
1. Prefer explicit, readable code over clever shortcuts.
2. Do not commit secrets, local databases, or generated artifacts.
3. Preserve existing API contracts unless the change explicitly versions them.
4. Add or update tests when behavior changes.
