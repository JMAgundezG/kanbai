import { Alert, Button, Form, Input, Label, Modal, TextField, useOverlayState } from '@heroui/react'
import { type FormEvent, useState } from 'react'

import { BOARD_NAME_MAX_LENGTH } from '@/features/board/api'
import { useCreateBoard } from '@/features/board/hooks'

/**
 * Botón "Nuevo tablero" y el diálogo que abre. Como en `LoginForm`, aquí solo vive el
 * estado de la interfaz (el nombre escrito y el aviso de campo vacío): la llamada y su
 * efecto sobre la caché son cosa de `useCreateBoard`.
 *
 * El diálogo es el `Modal` de HeroUI, que se apoya en React Aria: foco atrapado,
 * cierre con Escape y nombre accesible tomado de `Modal.Heading` vienen de serie.
 */
export function CreateBoardButton() {
  const [name, setName] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const createBoardMutation = useCreateBoard()

  // Cerrar —con el botón, con Escape o pulsando fuera— siempre deja el formulario
  // limpio, para que reabrirlo no muestre el error del intento anterior.
  const state = useOverlayState({
    onOpenChange: (isOpen) => {
      if (!isOpen) {
        setName('')
        setValidationError(null)
        createBoardMutation.reset()
      }
    },
  })

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedName = name.trim()

    if (!trimmedName) {
      setValidationError('Escribe un nombre para el tablero.')
      return
    }

    setValidationError(null)
    createBoardMutation.mutate({ name: trimmedName }, { onSuccess: () => state.close() })
  }

  const errorMessage =
    validationError ?? (createBoardMutation.isError ? createBoardMutation.error.message : null)

  return (
    <Modal state={state}>
      <Button>Nuevo tablero</Button>

      <Modal.Backdrop>
        <Modal.Container size="sm">
          <Modal.Dialog>
            <Modal.Header>
              <Modal.Heading>Nuevo tablero</Modal.Heading>
            </Modal.Header>

            <Form onSubmit={handleSubmit}>
              <Modal.Body>
                <div className="flex flex-col gap-4">
                  {/* Sin `isRequired` por el mismo motivo que en LoginForm: los
                      mensajes nativos del navegador salen en el idioma del sistema. */}
                  <TextField
                    value={name}
                    onChange={setName}
                    isDisabled={createBoardMutation.isPending}
                    autoFocus
                  >
                    <Label>Nombre</Label>
                    <Input maxLength={BOARD_NAME_MAX_LENGTH} />
                  </TextField>

                  {errorMessage ? (
                    <Alert status="danger">
                      <Alert.Title>No se pudo crear el tablero</Alert.Title>
                      <Alert.Description>{errorMessage}</Alert.Description>
                    </Alert>
                  ) : null}
                </div>
              </Modal.Body>

              <Modal.Footer>
                <Button
                  variant="ghost"
                  onPress={() => {
                    state.close()
                  }}
                  isDisabled={createBoardMutation.isPending}
                >
                  Cancelar
                </Button>
                <Button type="submit" isDisabled={createBoardMutation.isPending}>
                  {createBoardMutation.isPending ? 'Creando…' : 'Crear tablero'}
                </Button>
              </Modal.Footer>
            </Form>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal>
  )
}
