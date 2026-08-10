// Parcours navigateur de bout en bout : import du modèle, génération, rapport.
// Usage : node tests/ui_smoke.mjs
import { chromium } from 'playwright'

const shots = 'temp/shots'
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
const page = await browser.newPage({ viewport: { width: 1280, height: 1400 } })
const failures = []

const check = (label, ok, detail = '') => {
  console.log(`${ok ? '✓' : '✗'} ${label}${detail ? ' — ' + detail : ''}`)
  if (!ok) failures.push(label)
}

page.on('pageerror', (error) => failures.push(`erreur JS : ${error.message}`))

await page.goto('http://localhost:3000/', { waitUntil: 'networkidle' })
check('page chargée', (await page.title()) === 'Palab Dossier Generator')
check('titre affiché', await page.getByText('Palab Dossier Generator').first().isVisible())
check('avertissement données fictives visible',
  await page.getByText(/personnages fictifs de démonstration/).isVisible())
await page.screenshot({ path: `${shots}/01-accueil.png`, fullPage: true })

await page.setInputFiles('input[type=file]', 'palabdossiercollecte.xlsx')
await page.waitForSelector('text=modèle analysé', { timeout: 20000 })
check('modèle analysé et feuilles listées',
  await page.getByText('Lisez-moi, Femmes, Agents, Photos, Listes').isVisible())
check('colonnes retenues affichées', (await page.getByText('45').first().isVisible()))
check('colonnes non renseignées signalées',
  await page.getByText(/Colonnes non renseignées automatiquement/).isVisible())
await page.screenshot({ path: `${shots}/02-modele-analyse.png`, fullPage: true })

check('formulaire de configuration affiché',
  await page.getByText('2 · Configuration').isVisible())
check('options avancées présentes', await page.getByText('3 · Options avancées').isVisible())
check('résumé présent', await page.getByText('4 · Résumé').isVisible())

await page.getByRole('button', { name: 'Tester avec 3 profils' }).click()
await page.waitForSelector('text=Dossier terminé', { timeout: 120000 })
check('génération terminée', true)

const report = await page.locator('pre').first().innerText()
check('rapport de validation affiché', report.includes('3 profils générés'), report.split('\n')[0])
check('bouton ZIP présent',
  await page.getByRole('link', { name: 'Télécharger le ZIP complet' }).isVisible())
check('bouton Excel présent',
  await page.getByRole('link', { name: 'Télécharger Excel' }).isVisible())
await page.screenshot({ path: `${shots}/03-genere.png`, fullPage: true })

await page.getByRole('button', { name: 'Historique' }).click()
await page.waitForSelector('table', { timeout: 15000 })
const rows = await page.locator('tbody tr').count()
check('historique renseigné', rows > 0, `${rows} lignes`)
await page.screenshot({ path: `${shots}/04-historique.png`, fullPage: true })

await browser.close()
console.log(failures.length ? `\n${failures.length} ÉCHEC(S) : ${failures.join(', ')}` : '\nPARCOURS UI CONFORME')
process.exit(failures.length ? 1 : 0)
