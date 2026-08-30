import { Alert, Button, Form, Input, Label, TextField } from '@heroui/react'
import { type FormEvent, useState } from 'react'

import type { Actor } from '@/features/auth/api'
import { useLogin } from '@/features/auth/hooks'

interface LoginFormProps {
  /** Routing is the caller's concern, not the form's — kept out so this
   *  component stays testable without a router. */
  onSuccess?: (actor: Actor) => void
}

/**
 * Dumb-ish on purpose: the mutation and its cache effects live in `useLogin`.
 * What stays here is UI-only state (the two field values) and the client-side
 * "did you fill this in" check — deliberately not the browser's native
 * validation messages, which come in whatever language the OS is set to, not
 * Spanish.
 */
export function LoginForm({ onSuccess }: LoginFormProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const loginMutation = useLogin()

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!email.trim() || !password) {
      setValidationError('Introduce tu email y tu contraseña.')
      return
    }

    setValidationError(null)
    loginMutation.mutate(
      { email: email.trim(), password },
      {
        // Called with (data, variables, context) — narrowed to just the actor
        // so the prop's signature stays simple for callers.
        onSuccess: (actor) => onSuccess?.(actor),
      },
    )
  }

  const errorMessage = validationError ?? (loginMutation.isError ? loginMutation.error.message : null)

  return (
    <Form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {/* No `isRequired`: that turns on the browser's native constraint
          validation, whose messages come in the OS language, not Spanish.
          Emptiness is checked by hand in `handleSubmit` instead. */}
      <TextField
        type="email"
        value={email}
        onChange={setEmail}
        isDisabled={loginMutation.isPending}
        autoComplete="email"
      >
        <Label>Email</Label>
        <Input />
      </TextField>

      <TextField
        type="password"
        value={password}
        onChange={setPassword}
        isDisabled={loginMutation.isPending}
        autoComplete="current-password"
      >
        <Label>Contraseña</Label>
        <Input />
      </TextField>

      {errorMessage ? (
        <Alert status="danger">
          <Alert.Title>No se puede acceder</Alert.Title>
          <Alert.Description>{errorMessage}</Alert.Description>
        </Alert>
      ) : null}

      <Button type="submit" isDisabled={loginMutation.isPending} fullWidth>
        {loginMutation.isPending ? 'Accediendo…' : 'Acceder'}
      </Button>
    </Form>
  )
}
