// Vérifie qu'une valeur refusée est bloquée en amont, et qu'une erreur de
// validation venue du serveur s'affiche en français au lieu de « [object Object] ».
import { chromium } from 'playwright'

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
const page = await browser.newPage({ viewport: { width: 1100, height: 1400 } })
const failures = []
const check = (label, ok, detail = '') => {
  console.log(`${ok ? '✓' : '✗'} ${label}${detail ? ' — ' + detail : ''}`)
  if (!ok) failures.push(label)
}

await page.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' })
await page.setInputFiles('input[type=file]', 'palabdossiercollecte.xlsx')
await page.waitForSelector('text=modèle analysé', { timeout: 20000 })

// 1. Un champ vidé bloque les deux boutons, avec la raison affichée.
await page.locator('#start').fill('')
await page.waitForTimeout(250)
check(
  'raison affichée quand le premier numéro est vide',
  await page.getByText('Le premier numéro doit valoir au moins 1.').isVisible(),
)
check(
  'bouton principal désactivé',
  await page.getByRole('button', { name: 'GÉNÉRER LE DOSSIER' }).isDisabled(),
)
check(
  'bouton de test désactivé',
  await page.getByRole('button', { name: 'Tester avec 3 profils' }).isDisabled(),
)

// Le bouton de test impose 3 profils : un compteur vide ne doit pas le bloquer.
await page.locator('#start').fill('1')
await page.locator('#count').fill('')
await page.waitForTimeout(250)
check(
  'compteur vide : le bouton principal est bloqué',
  await page.getByRole('button', { name: 'GÉNÉRER LE DOSSIER' }).isDisabled(),
)
check(
  'compteur vide : le bouton de test reste utilisable',
  !(await page.getByRole('button', { name: 'Tester avec 3 profils' }).isDisabled()),
)

// 2. Champs revenus à des valeurs saines : tout se débloque.
await page.locator('#start').fill('1')
await page.locator('#count').fill('3')
await page.waitForTimeout(250)
check(
  'boutons réactivés une fois les valeurs corrigées',
  !(await page.getByRole('button', { name: 'GÉNÉRER LE DOSSIER' }).isDisabled()),
)

// 3. Le serveur refuse malgré tout : le message doit rester lisible.
await page.route('**/api/jobs', (route) =>
  route.fulfill({
    status: 422,
    contentType: 'application/json',
    body: JSON.stringify({
      detail: [
        {
          type: 'greater_than_equal',
          loc: ['body', 'start_number'],
          msg: 'Input should be greater than or equal to 1',
          ctx: { ge: 1 },
        },
      ],
    }),
  }),
)
await page.getByRole('button', { name: 'Tester avec 3 profils' }).click()
await page.waitForSelector('text=Valeurs refusées par le serveur', { timeout: 15000 })
const message = await page.getByText(/Valeurs refusées par le serveur/).innerText()
check('message de validation lisible', !message.includes('[object Object]'), message)
check('champ nommé en français', message.includes('Premier numéro'))

await page.screenshot({ path: 'temp/shots/erreurs.png', fullPage: true })
await browser.close()
console.log(failures.length ? `\n${failures.length} ÉCHEC(S)` : '\nGESTION DES ERREURS CONFORME')
process.exit(failures.length ? 1 : 0)
