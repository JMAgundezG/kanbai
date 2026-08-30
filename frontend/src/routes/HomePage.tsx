import { BackendStatusCard } from '@/features/health/components/BackendStatusCard'

export function HomePage() {
  return (
    // .row/.col-* come from Bootstrap's grid; spacing and type come from Tailwind.
    <div className="row g-4">
      <div className="col-12 col-md-6">
        <BackendStatusCard />
      </div>
      <div className="col-12 col-md-6">
        <h2 className="text-xl font-semibold">Bienvenido a kanbai</h2>
        <p className="mt-2 text-sm opacity-80">
          El tablero todavía no existe: esta pantalla solo comprueba que el frontend
          habla con la API y que los estilos cargan.
        </p>
      </div>
    </div>
  )
}
