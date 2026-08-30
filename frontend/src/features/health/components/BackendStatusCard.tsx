import { Alert, Card, Chip, Spinner } from '@heroui/react'

import { useBackendStatus } from '@/features/health/hooks'

/**
 * Dumb on purpose: the hook owns the data, this only renders it. The three states
 * every view must handle (loading, error, data) are explicit — CLAUDE.md § 5.
 */
export function BackendStatusCard() {
  const { data, isPending, isError, error } = useBackendStatus()

  if (isPending) {
    return (
      <Card>
        <Card.Content>
          {/* The flex layout goes on a plain div: Card.Content brings its own
              flex-direction, which a utility class for `display` alone cannot undo. */}
          <div className="flex items-center gap-3">
            <Spinner size="sm" aria-label="Comprobando el backend" />
            <span>Comprobando el estado del backend…</span>
          </div>
        </Card.Content>
      </Card>
    )
  }

  if (isError) {
    return (
      <Alert status="danger">
        <Alert.Title>No se puede contactar con el backend</Alert.Title>
        <Alert.Description>
          {error.message} Comprueba que la API está levantada con{' '}
          <code>uv run poe dev</code>.
        </Alert.Description>
      </Alert>
    )
  }

  return (
    <Card>
      <Card.Header>
        <Card.Title>Estado del backend</Card.Title>
      </Card.Header>
      <Card.Content>
        <div className="flex items-center gap-3">
          <span>Base de datos</span>
          <Chip color={data.database === 'ok' ? 'success' : 'danger'}>
            {data.database === 'ok' ? 'disponible' : 'no disponible'}
          </Chip>
        </div>
      </Card.Content>
    </Card>
  )
}
