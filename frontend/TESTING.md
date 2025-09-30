# Testing Guide

## Quick Start

```bash
# Run tests in watch mode (recommended for development)
npm test

# Run tests once
npm run test:run

# Run tests with coverage
npm run test:coverage

# Open interactive test UI
npm run test:ui
```

## Test Structure

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts
│   │   └── client.spec.ts          # API client unit tests
│   ├── stores/
│   │   ├── appointments.ts
│   │   └── appointments.spec.ts    # Store unit tests
│   ├── views/
│   │   ├── CalendarView.vue
│   │   ├── CalendarView.spec.ts    # Component tests
│   │   ├── HomeView.vue
│   │   └── HomeView.spec.ts
│   ├── test/
│   │   ├── setup.ts                # Global test setup
│   │   └── integration/
│   │       └── appointments.integration.spec.ts  # Integration tests
│   ├── App.vue
│   └── App.spec.ts                 # Root component tests
├── vitest.config.ts                # Vitest configuration
└── TEST_SUMMARY.md                 # Detailed test documentation
```

## Writing Tests

### Component Tests

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MyComponent from './MyComponent.vue'

describe('MyComponent', () => {
  it('should render correctly', () => {
    const wrapper = mount(MyComponent, {
      props: { title: 'Test' },
    })

    expect(wrapper.text()).toContain('Test')
  })
})
```

### Store Tests

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useMyStore } from './myStore'
import apiClient from '@/api/client'

vi.mock('@/api/client')

describe('MyStore', () => {
  let store: ReturnType<typeof useMyStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useMyStore()
    vi.clearAllMocks()
  })

  it('should fetch data', async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { items: [], total: 0 },
    })

    await store.fetchData()

    expect(store.items).toEqual([])
    expect(apiClient.get).toHaveBeenCalledWith('/endpoint')
  })
})
```

### Integration Tests

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useMyStore } from '@/stores/myStore'
import apiClient from '@/api/client'

vi.mock('@/api/client')

describe('Feature Integration', () => {
  it('should complete full flow', async () => {
    const store = useMyStore()

    // Mock backend response
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { id: '1', name: 'Test' },
    })

    // Execute action
    const result = await store.create({ name: 'Test' })

    // Verify integration
    expect(result.id).toBe('1')
    expect(store.items).toContainEqual(result)
  })
})
```

## Coverage Thresholds

- **Lines**: 85%
- **Functions**: 85%
- **Branches**: 80%
- **Statements**: 85%

Coverage excludes:

- Generated files (`src/api/schema.ts`)
- Configuration files
- Router setup
- Main entry point

## Debugging Tests

### 1. Run specific test file

```bash
npm run test:run -- src/stores/appointments.spec.ts
```

### 2. Run tests matching pattern

```bash
npm run test:run -- -t "should fetch"
```

### 3. Use test UI for debugging

```bash
npm run test:ui
```

Opens http://localhost:51204/**vitest**/ with interactive test explorer.

### 4. Add console.log in tests

```typescript
it('should debug', () => {
  console.log(wrapper.html()) // Prints component HTML
  console.log(store.items) // Prints store state
})
```

## CI/CD Integration

Tests run automatically in CI with:

```bash
npm run test:run
```

This command:

- Runs all tests once
- Exits with code 0 (success) or 1 (failure)
- Does not watch for changes

Example GitHub Actions:

```yaml
- name: Install dependencies
  run: npm ci

- name: Run tests
  run: npm run test:run

- name: Generate coverage
  run: npm run test:coverage
```

## Common Issues

### Issue: "Cannot find module '@/...'"

**Solution**: Check `vite.config.ts` has correct alias configuration:

```typescript
resolve: {
  alias: {
    '@': fileURLToPath(new URL('./src', import.meta.url))
  }
}
```

### Issue: Tests timeout

**Solution**: Increase timeout in test:

```typescript
it('slow test', async () => {
  // ...
}, 10000) // 10 second timeout
```

### Issue: Mock not working

**Solution**: Ensure mock is defined before import:

```typescript
// ❌ Wrong order
import { useMyStore } from './myStore'
vi.mock('@/api/client')

// ✅ Correct order
vi.mock('@/api/client')
import { useMyStore } from './myStore'
```

### Issue: Store state persists between tests

**Solution**: Create fresh Pinia instance in `beforeEach`:

```typescript
beforeEach(() => {
  setActivePinia(createPinia())
  store = useMyStore()
})
```

## Next Steps

1. Read [TEST_SUMMARY.md](./TEST_SUMMARY.md) for detailed test documentation
2. Run `npm run test:ui` to explore existing tests
3. Add tests for new features before implementation (TDD)
4. Maintain >85% coverage for all new code

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [Vue Test Utils](https://test-utils.vuejs.org/)
- [Testing Pinia](https://pinia.vuejs.org/cookbook/testing.html)
