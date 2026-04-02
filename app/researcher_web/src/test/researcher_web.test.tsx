import { render, screen } from '@testing-library/react'
import App from '../App'

describe('researcher web shell', () => {
  it('renders admin title and key tabs', () => {
    render(<App />)
    expect(screen.getByText('CABDI Researcher Admin (MVP)')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'upload' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'diagnostics' })).toBeInTheDocument()
  })
})
