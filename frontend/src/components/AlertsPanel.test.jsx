import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import AlertsPanel from './AlertsPanel'
import { getAlerts } from '../services/api'

vi.mock('../services/api', () => ({
  getAlerts: vi.fn(),
}))

const result = (alerts) => ({ days: 7, window_start: null, window_end: null, alerts })

const veryLow = {
  rule: 'very_low', severity: 'urgent', emergency: true,
  title: 'Very low glucose: 48 mg/dL', detail: 'Below 54 mg/dL on Oct 31 at 20:00. This demo contacts no one.',
}
const high = {
  rule: 'high', severity: 'warning', emergency: false,
  title: '40% of readings above 180 mg/dL', detail: 'Goal is under 25% of readings above 180 mg/dL.',
}
const inRange = {
  rule: 'in_range', severity: 'info', emergency: false,
  title: 'Time in range: 58%', detail: '120 readings in the last 7 days.',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AlertsPanel', () => {
  it('lists alerts with their severity', async () => {
    getAlerts.mockResolvedValue(result([high, inRange]))
    render(<AlertsPanel patientId="p-1" />)

    expect(await screen.findByText('40% of readings above 180 mg/dL')).toBeInTheDocument()
    expect(screen.getByText('Time in range: 58%')).toBeInTheDocument()
    expect(screen.getByText('Check')).toBeInTheDocument()
    expect(screen.getByText('Info')).toBeInTheDocument()
    expect(getAlerts).toHaveBeenCalledWith('p-1', 7)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a very low reading as a simulated emergency, once', async () => {
    getAlerts.mockResolvedValue(result([veryLow, high]))
    render(<AlertsPanel patientId="p-1" />)

    const emergency = await screen.findByRole('alert')
    expect(emergency).toHaveTextContent('Very low glucose: 48 mg/dL')
    expect(screen.getAllByText('Very low glucose: 48 mg/dL')).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Call emergency services (simulated)' })).toBeDisabled()
  })

  it('says when there are no alerts', async () => {
    getAlerts.mockResolvedValue(result([]))
    render(<AlertsPanel patientId="p-1" />)

    expect(await screen.findByText(/No alerts/)).toBeInTheDocument()
  })

  it('shows an error when alerts cannot load', async () => {
    getAlerts.mockRejectedValue(new Error('API request failed (500)'))
    render(<AlertsPanel patientId="p-1" />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load alerts: API request failed (500)')
  })

  it('reloads when refreshKey changes', async () => {
    getAlerts.mockResolvedValue(result([inRange]))
    const { rerender } = render(<AlertsPanel patientId="p-1" refreshKey={0} />)
    await screen.findByText('Time in range: 58%')

    getAlerts.mockResolvedValue(result([veryLow]))
    rerender(<AlertsPanel patientId="p-1" refreshKey={1} />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Very low glucose: 48 mg/dL')
    expect(getAlerts).toHaveBeenCalledTimes(2)
  })
})
