
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect } from 'vitest'
import ManualLogging from './ManualLogging'

describe('ManualLogging', () => {
  it('displays the glucose form by default', () => {
    render(<ManualLogging patientId="test-patient" />)

    expect(
      screen.getByRole('heading', { name: 'Log Glucose Reading' })
    ).toBeInTheDocument()

    expect(
      screen.getByLabelText('Blood Glucose (mg/dL)')
    ).toBeInTheDocument()
  })

  it('switches to the insulin form', async () => {
    const user = userEvent.setup()

    render(<ManualLogging patientId="test-patient" />)

    await user.click(screen.getByRole('button', { name: 'Insulin' }))

    expect(
      screen.getByRole('heading', { name: 'Log Insulin Dose' })
    ).toBeInTheDocument()

    expect(
      screen.getByLabelText('Insulin Dose (units)')
    ).toBeInTheDocument()
  })
})


  it('switches to the nutrition form', async () => {
    const user = userEvent.setup()
    render(<ManualLogging patientId="test-patient" />)

    await user.click(screen.getByRole('button', { name: 'Nutrition' }))

    expect(
      screen.getByRole('heading', { name: 'Log Meal' })
    ).toBeInTheDocument()

    expect(
      screen.getByLabelText('Meal Description')
    ).toBeInTheDocument()
  })

  it('allows glucose values to be entered', async () => {
    const user = userEvent.setup()
    render(<ManualLogging patientId="test-patient" />)

    const input = screen.getByLabelText('Blood Glucose (mg/dL)')

    await user.type(input, '120')

    expect(input).toHaveValue(120)
  })

  it('preserves glucose values when switching tabs', async () => {
    const user = userEvent.setup()
    render(<ManualLogging patientId="test-patient" />)

    await user.type(
      screen.getByLabelText('Blood Glucose (mg/dL)'),
      '145'
    )

    await user.click(screen.getByRole('button', { name: 'Insulin' }))
    await user.click(screen.getByRole('button', { name: 'Glucose' }))

    expect(
      screen.getByLabelText('Blood Glucose (mg/dL)')
    ).toHaveValue(145)
  })

  it('disables saving until backend support is available', async () => {
    const user = userEvent.setup()
    render(<ManualLogging patientId="test-patient" />)

    expect(
      screen.getByRole('button', { name: 'Save Glucose Reading' })
    ).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Insulin' }))

    expect(
      screen.getByRole('button', { name: 'Save Insulin Dose' })
    ).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Nutrition' }))

    expect(
      screen.getByRole('button', { name: 'Save Meal' })
    ).toBeDisabled()
  })

  it('explains why saving is unavailable', () => {
    render(<ManualLogging patientId="test-patient" />)

    expect(
      screen.getByRole('status')
    ).toHaveTextContent('Saving is not yet available')
  })

