import fs from "node:fs/promises";
import path from "node:path";

async function main() {
  const args = process.argv.slice(2);
  const archiveDir = args[0]
    ? path.resolve(process.cwd(), args[0])
    : path.resolve(process.cwd(), "Podatki bank", "archive");

  const outputPath = args[1]
    ? path.resolve(process.cwd(), args[1])
    : path.resolve(process.cwd(), "offers.json");

  // Prefer the current all_banks.csv (freshly created by vse_banke_depoziti.py)
  // so "latest" always means the newest day, including today.
  const currentAllBanksPath = path.resolve(process.cwd(), "Podatki bank", "all_banks.csv");
  try {
    await fs.stat(currentAllBanksPath);

    const generatorPath = path.resolve(process.cwd(), "scripts", "generate-offers.mjs");
    const { spawn } = await import("node:child_process");

    console.log(`Using latest source: ${currentAllBanksPath}`);

    const child = spawn(process.execPath, [generatorPath, currentAllBanksPath, outputPath], {
      stdio: "inherit",
      cwd: process.cwd()
    });

    child.on("exit", (code) => {
      process.exit(code ?? 1);
    });

    return;
  } catch {
    // fall back to archive scanning below
  }

  const dirents = await fs.readdir(archiveDir, { withFileTypes: true });
  const candidates = dirents
    .filter((d) => d.isFile())
    .map((d) => d.name)
    .filter((name) => /^all_banks_\d{4}-\d{2}-\d{2}\.csv$/i.test(name))
    .sort();

  if (candidates.length === 0) {
    console.error(`No all_banks_YYYY-MM-DD.csv found in ${archiveDir}`);
    process.exit(1);
  }

  const latest = candidates[candidates.length - 1];
  const latestPath = path.join(archiveDir, latest);

  const generatorPath = path.resolve(process.cwd(), "scripts", "generate-offers.mjs");
  const { spawn } = await import("node:child_process");

  console.log(`Using latest source: ${latestPath}`);

  const child = spawn(process.execPath, [generatorPath, latestPath, outputPath], {
    stdio: "inherit",
    cwd: process.cwd()
  });

  child.on("exit", (code) => {
    process.exit(code ?? 1);
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
