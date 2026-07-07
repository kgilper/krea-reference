export const meta = {
  name: 'recipe-tweak-test',
  description: 'Rapid ComfyUI recipe tweak-and-test: Haiku agents render variants, a Fable agent judges them against intent',
  phases: [{ title: 'Render', detail: 'cheap agents render each variant on ComfyUI' }, { title: 'Judge', detail: 'Fable judges variants against the recipe intent' }],
}

const RAW_ARGS = (typeof args === 'undefined') ? {} : args
const A = (RAW_ARGS && typeof RAW_ARGS === 'string') ? JSON.parse(RAW_ARGS) : (RAW_ARGS || {})
const ENV = globalThis.process?.env || {}
const opt = (name, fallback) => (A[name] || ENV[`KREA_REFERENCE_${name.toUpperCase()}`] || fallback)
const trimTrailingSlash = value => String(value).replace(/[\\/]+$/, '')

const REPO = trimTrailingSlash(opt('repo', globalThis.process?.cwd?.() || '.'))
const TWEAK = 'docs/recipe-lab/tweak_test.py'
const SCRATCH = trimTrailingSlash(opt('scratch', `${REPO}/docs/recipe-lab/runs/scratchpad`))

const DEFAULT_JOBS = [
  { label: 'suggest the visual style', intent: "Borrow the reference vase's colors and painterly finish onto the prompt's plain bowl, WITHOUT turning the bowl into the vase (keep the bowl shape/subject).", ref_input: 'layerprobe2/base.png', ref_local: `${REPO}/docs/recipe-lab/refs/base.png`, prompt: 'a plain smooth white ceramic bowl on a light wooden table, soft even studio light, no text', strength: 0.6, seed: 424242,
    variants: [
      { name: 'style-current-0p6', builtin: 'suggest the visual style', strength: 0.6 },
      { name: 'style-strong-0p9', builtin: 'suggest the visual style', strength: 0.9 },
      { name: 'style-modelaligned', strength: 0.6, bundle: { label: 'style modelaligned', role: 'style', treatment: 'palette wash', color: 0.85, detail: 0.05, study: '384', framing: 'stack', subject: 'avoid', early: 0.85, late: 0.85, guard: false, cap: 0.9, shape: 0.35, global: 1.85, layers: [0.11,0.31,0.72,0.98,1.38,0.77,0.78,2.8,1.0,1.74,1.19,0.22] } },
    ] },
  { label: 'suggest the color palette', intent: "Shift the bowl scene's COLORS toward the reference vase's palette only, without copying the vase's shapes, patterns, or subject.", ref_input: 'layerprobe2/base.png', ref_local: `${REPO}/docs/recipe-lab/refs/base.png`, prompt: 'a plain smooth white ceramic bowl on a light wooden table, soft even studio light, no text', strength: 0.85, seed: 424242,
    variants: [
      { name: 'palette-current-0p85', builtin: 'suggest the color palette', strength: 0.85 },
      { name: 'palette-strong-1p2', builtin: 'suggest the color palette', strength: 1.2 },
    ] },
]

const RENDER_SCHEMA = { type: 'object', properties: { name: { type: 'string' }, image: { type: 'string' }, metrics: { type: 'object' } }, required: ['name', 'image'] }
const JUDGE_SCHEMA = { type: 'object', properties: { scores: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, score: { type: 'number' }, notes: { type: 'string' } }, required: ['name', 'score'] } }, best: { type: 'string' }, verdict: { type: 'string' }, recommended: { type: 'string' } }, required: ['scores', 'best', 'verdict', 'recommended'] }

function renderPrompt(job, v) {
  const common = `--ref "${job.ref_input}" --prompt "${job.prompt}" --strength ${v.strength ?? job.strength} --seed ${job.seed} --name "${v.name}"`
  if (v.bundle) {
    return `Do ONE mechanical render, no judgment. Working dir: ${REPO}.
1. Write this exact JSON to ${SCRATCH}/${v.name}.json:
${JSON.stringify(v.bundle)}
2. Run: python ${TWEAK} --recipe-json "${SCRATCH}/${v.name}.json" ${common}
It prints one JSON line {name,image,metrics}. Return that object as structured output. Retry once on error.`
  }
  return `Do ONE mechanical render, no judgment. Working dir: ${REPO}.
Run: python ${TWEAK} --builtin "${v.builtin}" ${common}
It prints one JSON line {name,image,metrics}. Return that object as structured output. Retry once on error.`
}

function judgePrompt(job, rendered) {
  const list = rendered.map(r => `- ${r.name}: image ${r.image}  metrics ${JSON.stringify(r.metrics || {})}`).join('\n')
  return `You are the JUDGE for a ComfyUI image-recipe. Judge purely from the rendered images you Read.

Recipe: "${job.label}"
Intended job: ${job.intent}
Reference image (what the card borrows FROM): Read it at ${job.ref_local}
Content prompt (the subject that should be kept): "${job.prompt}"

Read EVERY candidate image below, then score 0-10 how well each achieves the intended job WITHOUT overstepping (a style card borrows look but keeps the prompt's subject; a palette card shifts color only).
Candidates:
${list}

Return scores [{name,score,notes}] for every candidate, the single best name, a one-line verdict, and a concrete 'recommended' settings change if the current variant underperforms (else "keep current"). Judge only from what you see.`
}

const jobs = (A.jobs && A.jobs.length) ? A.jobs : DEFAULT_JOBS
log(`testing ${jobs.length} recipes`)

const results = await pipeline(
  jobs,
  async (job) => {
    const rendered = await parallel(job.variants.map(v => () =>
      agent(renderPrompt(job, v), { label: `render:${v.name}`, phase: 'Render', model: 'haiku', schema: RENDER_SCHEMA })
    ))
    return { job, rendered: rendered.filter(Boolean) }
  },
  async ({ job, rendered }) => {
    if (!rendered.length) return { label: job.label, error: 'no renders' }
    const verdict = await agent(judgePrompt(job, rendered), { label: `judge:${job.label}`, phase: 'Judge', model: 'fable', schema: JUDGE_SCHEMA })
    return { label: job.label, intent: job.intent, rendered: rendered.map(r => ({ name: r.name, image: r.image, metrics: r.metrics })), verdict }
  }
)
return results
