# PazPaz Frontend

Vue 3 + TypeScript + Tailwind CSS frontend for PazPaz practice management application.

## Setup

1. Install dependencies:
```bash
npm install
```

## Development

Run development server:
```bash
npm run dev
```

Build for production:
```bash
npm run build
```

Preview production build:
```bash
npm run preview
```

Lint:
```bash
npm run lint
```

Format:
```bash
npm run format
```

## Project Structure

```
frontend/
├── src/
│   ├── components/    # Reusable Vue components
│   ├── composables/   # Composition API composables
│   ├── stores/        # Pinia state management
│   ├── views/         # Page components
│   ├── App.vue        # Root component
│   ├── main.ts        # Application entry point
│   └── style.css      # Global styles (Tailwind)
└── public/            # Static assets
```

## Tech Stack

- **Vue 3**: Composition API with `<script setup>`
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling
- **Vite**: Fast build tool and dev server
- **ESLint**: Code linting
- **Prettier**: Code formatting