import pkg from '/Users/aaravagarwal/.npm/_npx/e41f203b7505f1fb/node_modules/playwright/index.js';
const { chromium } = pkg;
import { execSync } from 'child_process';

// Get a fresh token
const res = await fetch('http://localhost:8000/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'screenshot@bot.local', password: 'botpass123' }),
});
const { token, user } = await res.json();
if (!token) { console.error('Login failed'); process.exit(1); }

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  viewport: { width: 1400, height: 900 },
  deviceScaleFactor: 2,
});

async function seedAuth(page) {
  await page.goto('http://localhost:5173', { waitUntil: 'domcontentloaded' });
  await page.evaluate(({ token, user }) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
  }, { token, user });
}

// ── 1. Dashboard ──────────────────────────────────────────────────────────────
{
  const page = await ctx.newPage();
  await seedAuth(page);
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });
  // Wait for dashboard content
  await page.waitForSelector('.dashboard-grid, .dashboard-page, h1, .upload-btn', { timeout: 10000 });
  await page.waitForTimeout(1200); // let charts/animations settle
  await page.screenshot({ path: '/Users/aaravagarwal/Desktop/finance-categorizer/screenshots/dashboard.png', fullPage: false });
  console.log('✓ dashboard.png');
  await page.close();
}

// ── 2. AMEX statement transaction table ───────────────────────────────────────
{
  const page = await ctx.newPage();
  await seedAuth(page);
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });

  // Click History nav link
  await page.waitForSelector('button:has-text("History")', { timeout: 8000 });
  await page.click('button:has-text("History")');
  await page.waitForTimeout(600);

  // Click the most recent AMEX statement
  await page.waitForSelector('text=Amex', { timeout: 8000 });
  const amexLinks = page.locator('button:has-text("View"), .history-view-btn, button').filter({ hasText: /view/i });
  // Find the row that contains an Amex label and click View on it
  const amexRow = page.locator('.upload-row, .history-row, li, .card').filter({ hasText: /amex.*may|13th may/i }).first();
  const viewBtn = amexRow.locator('button').filter({ hasText: /view/i }).first();
  await viewBtn.click({ timeout: 8000 }).catch(async () => {
    // Fallback: click the first visible View button in the list
    await page.locator('button').filter({ hasText: /^view$/i }).first().click();
  });

  await page.waitForSelector('table, .txn-table, .transaction-row, tr', { timeout: 12000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: '/Users/aaravagarwal/Desktop/finance-categorizer/screenshots/transactions.png', fullPage: false });
  console.log('✓ transactions.png');
  await page.close();
}

// ── 3. View All 2026 spending charts ─────────────────────────────────────────
{
  const page = await ctx.newPage();
  await seedAuth(page);
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });

  // Click History
  await page.waitForSelector('button:has-text("History")', { timeout: 8000 });
  await page.click('button:has-text("History")');
  await page.waitForTimeout(600);

  // Click "View All 2026"
  await page.waitForSelector('button:has-text("View All 2026")', { timeout: 8000 });
  await page.click('button:has-text("View All 2026")');

  // Wait for charts to render
  await page.waitForSelector('.recharts-wrapper, svg, .spending-trends, .chart', { timeout: 12000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: '/Users/aaravagarwal/Desktop/finance-categorizer/screenshots/charts.png', fullPage: false });
  console.log('✓ charts.png');
  await page.close();
}

await browser.close();
console.log('Done — all 3 screenshots saved.');
