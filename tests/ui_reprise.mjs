import { chromium } from 'playwright'
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
const p = await b.newPage({ viewport: { width: 1100, height: 1500 } })
const fails = []
const ok = (l, c, d = '') => { console.log(`${c ? '✓' : '✗'} ${l}${d ? ' — ' + d : ''}`); if (!c) fails.push(l) }

await p.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' })
await p.setInputFiles('input[type=file]', 'temp/deja_rempli.xlsx')
await p.waitForSelector('text=modèle analysé', { timeout: 20000 })

const bandeau = await p.getByText(/profils déjà présents/).locator('..').innerText()
ok('profils existants détectés', bandeau.includes('5 profils déjà présent'), bandeau.replace(/\s+/g, ' ').slice(0, 130))
ok('reprise annoncée à PAL-0006', bandeau.includes('PAL-0006'))
ok('ligne d\'insertion annoncée', bandeau.includes('ligne 8'))

const start = await p.locator('#start').inputValue()
ok('champ « Premier numéro » prérempli', start === '6', `valeur=${start}`)

await p.locator('#count').fill('3')
await p.waitForTimeout(200)
const resume = await p.getByText('codes attribués').locator('..').innerText()
ok('plage annoncée dans le résumé', resume.includes('PAL-0006') && resume.includes('PAL-0008'), resume.replace(/\s+/g, ' '))

await p.locator('#start').fill('2')
await p.waitForTimeout(200)
ok('alerte si le numéro est trop bas', await p.getByText(/vous créeriez des doublons/).isVisible())
await p.locator('#start').fill('6')

await p.screenshot({ path: 'temp/shots/reprise.png', fullPage: true })
await p.getByRole('button', { name: 'Tester avec 3 profils' }).click()
await p.waitForSelector('text=Dossier terminé', { timeout: 180000 })
const rapport = await p.locator('pre').first().innerText()
ok('aucun conflit signalé', rapport.includes('aucun conflit avec les 5 codes'), rapport.split('\n').find(l => l.includes('conflit')) || '')
await b.close()
console.log(fails.length ? `\n${fails.length} ÉCHEC(S)` : '\nPARCOURS REPRISE CONFORME')
process.exit(fails.length ? 1 : 0)
