// @vitest-environment jsdom
/**
 * The outcome donut.
 *
 * Pass and fail are the two states a reader must never confuse, and measured
 * against each other Bud's emerald and red are the worst pair on the page:
 * CVD ΔE 2.1 under deuteranopia, which is roughly one man in twelve. So these
 * cases hold the chart to carrying identity by something other than colour -
 * a name, an icon and a count per segment - and to the arithmetic being right,
 * since a share that does not add up is worse than no chart.
 */
import { cleanup, render, screen, within } from '@testing-library/react'
import { CheckCircle, Clock, MinusCircle, XCircle } from 'lucide-react'
import { afterEach, describe, expect, it } from 'vitest'

import OutcomeDonut from '../components/OutcomeDonut'

const outcomes = [
  { label: 'Passed', value: 70, tone: 'text-emerald-600', icon: CheckCircle },
  { label: 'Failed', value: 20, tone: 'text-red-600', icon: XCircle },
  { label: 'Skipped', value: 10, tone: 'text-muted-foreground', icon: MinusCircle },
]

function renderDonut(props: Partial<React.ComponentProps<typeof OutcomeDonut>> = {}) {
  return render(
    <OutcomeDonut title="Test Outcomes" totalLabel="tests" segments={outcomes} {...props} />,
  )
}

/** The row in the legend for one outcome. */
function legendRow(label: string): HTMLElement {
  return screen.getByText(label).closest('li') as HTMLElement
}

/**
 * The arcs actually drawn, in order, excluding the background track.
 *
 * Scoped to the chart's own svg: the lucide icons in the legend are svgs full
 * of circles too, so a bare `querySelectorAll('circle')` counts glyphs as data.
 */
function arcs(container: HTMLElement): SVGCircleElement[] {
  const chart = container.querySelector('svg[role="img"]') as SVGElement
  return Array.from(chart.querySelectorAll('circle')).slice(1) as SVGCircleElement[]
}

afterEach(cleanup)

describe('what the donut tells the reader', () => {
  it('names every outcome rather than relying on the colour of an arc', () => {
    renderDonut()

    for (const outcome of outcomes) {
      expect(screen.getByText(outcome.label)).toBeTruthy()
    }
  })

  it('gives each outcome its own count and share', () => {
    renderDonut()

    expect(within(legendRow('Passed')).getByText('70')).toBeTruthy()
    expect(within(legendRow('Passed')).getByText('70%')).toBeTruthy()
    expect(within(legendRow('Failed')).getByText('20%')).toBeTruthy()
    expect(within(legendRow('Skipped')).getByText('10%')).toBeTruthy()
  })

  it('puts the total in the hole', () => {
    renderDonut()

    expect(screen.getByText('100')).toBeTruthy()
    expect(screen.getByText('tests')).toBeTruthy()
  })

  it('carries an icon alongside each colour', () => {
    const { container } = renderDonut()

    // Colour alone would leave pass and fail indistinguishable to a
    // deuteranope; every legend row pairs its colour with a glyph.
    for (const outcome of outcomes) {
      expect(legendRow(outcome.label).querySelector('svg')).toBeTruthy()
    }
    expect(container.querySelectorAll('li svg')).toHaveLength(outcomes.length)
  })

  it('describes each arc for a pointer and a screen reader', () => {
    const { container } = renderDonut()

    const titles = Array.from(container.querySelectorAll('circle title')).map((t) => t.textContent)
    expect(titles).toEqual(['Passed: 70 (70%)', 'Failed: 20 (20%)', 'Skipped: 10 (10%)'])
  })
})

describe('the arithmetic behind the arcs', () => {
  it('draws one arc per outcome that actually happened', () => {
    const { container } = renderDonut()

    expect(arcs(container)).toHaveLength(3)
  })

  it('sizes each arc by its share of the total', () => {
    const { container } = renderDonut()
    const circumference = 2 * Math.PI * 42

    const [passed] = arcs(container)
    const [length] = (passed.getAttribute('stroke-dasharray') ?? '').split(' ').map(Number)
    // 70% of the ring, less the gap that separates it from the next arc.
    expect(length).toBeCloseTo(0.7 * circumference - 3, 1)
  })

  it('starts each arc where the previous one ended', () => {
    const { container } = renderDonut()
    const circumference = 2 * Math.PI * 42
    const offsets = arcs(container).map((arc) => Number(arc.getAttribute('stroke-dashoffset')))

    // Offsets run negative as the ring fills: 0, then 70%, then 90%.
    expect(offsets[0]).toBeCloseTo(0, 5)
    expect(offsets[1]).toBeCloseTo(-0.7 * circumference, 1)
    expect(offsets[2]).toBeCloseTo(-0.9 * circumference, 1)
  })

  it('draws no arc for an outcome that did not happen', () => {
    const { container } = renderDonut({
      segments: [
        { label: 'Passed', value: 5, tone: 'text-emerald-600', icon: CheckCircle },
        { label: 'Failed', value: 0, tone: 'text-red-600', icon: XCircle },
        { label: 'Skipped', value: 0, tone: 'text-muted-foreground', icon: MinusCircle },
      ],
    })

    // A zero-length arc still paints its own end caps, which reads as a stray
    // tick on the ring.
    expect(arcs(container)).toHaveLength(1)
  })

  it('still lists an outcome that did not happen, as a zero', () => {
    renderDonut({
      segments: [
        { label: 'Passed', value: 5, tone: 'text-emerald-600', icon: CheckCircle },
        { label: 'Failed', value: 0, tone: 'text-red-600', icon: XCircle },
        { label: 'Skipped', value: 0, tone: 'text-muted-foreground', icon: MinusCircle },
      ],
    })

    // "No failures" is information; an absent row would just look like a
    // shorter legend.
    expect(within(legendRow('Failed')).getByText('0')).toBeTruthy()
    expect(within(legendRow('Failed')).getByText('0%')).toBeTruthy()
  })

  it('keeps each outcome on its own colour when another empties', () => {
    const { container } = renderDonut({
      segments: [
        { label: 'Passed', value: 0, tone: 'text-emerald-600', icon: CheckCircle },
        { label: 'Failed', value: 3, tone: 'text-red-600', icon: XCircle },
        { label: 'Skipped', value: 1, tone: 'text-muted-foreground', icon: MinusCircle },
      ],
    })

    // A filter that empties one outcome must not repaint the survivors, or
    // failures would be reading as passes.
    const drawn = arcs(container)
    expect(drawn[0].getAttribute('class')).toContain('text-red-600')
    expect(drawn[1].getAttribute('class')).toContain('text-muted-foreground')
  })

  it('says nothing rather than dividing by zero when there is no data', () => {
    const { container } = renderDonut({
      segments: [
        { label: 'Passed', value: 0, tone: 'text-emerald-600', icon: CheckCircle },
        { label: 'Failed', value: 0, tone: 'text-red-600', icon: XCircle },
      ],
    })

    expect(arcs(container)).toHaveLength(0)
    // "0" is the hero total and both legend counts, so scope to each.
    expect(within(legendRow('Passed')).getByText('0')).toBeTruthy()
    // 0/0 is not 0%, and printing one would be a claim the data cannot support.
    expect(within(legendRow('Passed')).getByText('—')).toBeTruthy()
    expect(within(legendRow('Failed')).getByText('—')).toBeTruthy()
  })

  it('rounds each share to a whole percent', () => {
    renderDonut({
      segments: [
        { label: 'Passed', value: 1, tone: 'text-emerald-600', icon: CheckCircle },
        { label: 'Failed', value: 2, tone: 'text-red-600', icon: XCircle },
      ],
    })

    expect(within(legendRow('Passed')).getByText('33%')).toBeTruthy()
    expect(within(legendRow('Failed')).getByText('67%')).toBeTruthy()
  })

  it('takes the segments in the order it was given', () => {
    const { container } = renderDonut({
      segments: [
        { label: 'In progress', value: 1, tone: 'text-amber-600', icon: Clock },
        { label: 'Passed', value: 1, tone: 'text-emerald-600', icon: CheckCircle },
      ],
    })

    const titles = Array.from(container.querySelectorAll('circle title')).map((t) => t.textContent)
    expect(titles[0]).toContain('In progress')
  })
})
