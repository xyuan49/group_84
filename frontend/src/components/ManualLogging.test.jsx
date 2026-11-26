
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ManualLogging from './ManualLogging'
import { createGlucose, createInsulin, createMeal } from '../services/api'

vi.mock('../services/api', () => ({
  createGlucose: vi.fn(),
  createInsulin: vi.fn(),
  createMeal: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

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

  it('saves a glucose reading', async () => {
    const user = userEvent.setup()
    const onGlucoseSaved = vi.fn()
    createGlucose.mockResolvedValue({})
    render(<ManualLogging patientId="test-patient" onGlucoseSaved={onGlucoseSaved} />)

    await user.type(screen.getByLabelText('Blood Glucose (mg/dL)'), '145')
    await user.type(screen.getByLabelText('Date and Time'), '2026-11-15T08:00')
    await user.click(screen.getByRole('button', { name: 'Save Glucose Reading' }))

    expect(createGlucose).toHaveBeenCalledWith('test-patient', {
      value_mg_dl: 145,
      measured_at: '2026-11-15T08:00',
      meal_context: 'fasting',
    })
    expect(onGlucoseSaved).toHaveBeenCalled()
    expect(screen.getByRole('status')).toHaveTextContent('Glucose reading saved.')
    expect(screen.getByLabelText('Blood Glucose (mg/dL)')).toHaveValue(null)
  })

  it('saves an insulin dose', async () => {
    const user = userEvent.setup()
    const onInsulinSaved = vi.fn()
    createInsulin.mockResolvedValue({})
    render(<ManualLogging patientId="test-patient" onInsulinSaved={onInsulinSaved} />)

    await user.click(screen.getByRole('button', { name: 'Insulin' }))
    await user.type(screen.getByLabelText('Insulin Dose (units)'), '8')
    await user.selectOptions(screen.getByLabelText('Insulin Type'), 'long')
    await user.type(screen.getByLabelText('Administration Date and Time'), '2026-11-15T21:00')
    await user.click(screen.getByRole('button', { name: 'Save Insulin Dose' }))

    expect(createInsulin).toHaveBeenCalledWith('test-patient', {
      units: 8,
      insulin_type: 'long',
      administered_at: '2026-11-15T21:00',
    })
    expect(onInsulinSaved).toHaveBeenCalled()
    expect(screen.getByRole('status')).toHaveTextContent('Insulin dose saved.')
  })

  it('saves a meal and sends empty optional fields as null', async () => {
    const user = userEvent.setup()
    createMeal.mockResolvedValue({})
    render(<ManualLogging patientId="test-patient" />)

    await user.click(screen.getByRole('button', { name: 'Nutrition' }))
    await user.type(screen.getByLabelText('Meal Description'), 'Apple')
    await user.type(screen.getByLabelText('Meal Date and Time'), '2026-11-15T15:00')
    await user.click(screen.getByRole('button', { name: 'Save Meal' }))

    expect(createMeal).toHaveBeenCalledWith('test-patient', {
      description: 'Apple',
      carbs_g: null,
      calories: null,
      eaten_at: '2026-11-15T15:00',
    })
    expect(screen.getByRole('status')).toHaveTextContent('Meal saved.')
  })

  it('shows an error and keeps the entry when saving fails', async () => {
    const user = userEvent.setup()
    const onInsulinSaved = vi.fn()
    createInsulin.mockRejectedValue(new Error('Could not save insulin dose (500)'))
    render(<ManualLogging patientId="test-patient" onInsulinSaved={onInsulinSaved} />)

    await user.click(screen.getByRole('button', { name: 'Insulin' }))
    await user.type(screen.getByLabelText('Insulin Dose (units)'), '8')
    await user.type(screen.getByLabelText('Administration Date and Time'), '2026-11-15T21:00')
    await user.click(screen.getByRole('button', { name: 'Save Insulin Dose' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Could not save insulin dose (500)')
    expect(screen.getByLabelText('Insulin Dose (units)')).toHaveValue(8)
    expect(onInsulinSaved).not.toHaveBeenCalled()
  })

  it('disables saving when no patient is selected', () => {
    render(<ManualLogging patientId="" />)

    expect(
      screen.getByRole('button', { name: 'Save Glucose Reading' })
    ).toBeDisabled()
  })
})
