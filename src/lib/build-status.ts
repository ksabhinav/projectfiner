import { execFileSync } from 'node:child_process';
import releaseCatalog from '../../public/releases/index.json';

const FRESHNESS_TARGET_DAYS = 365;

function gitValue(args: string[], fallback: string): string {
  try {
    return execFileSync('git', args, { encoding: 'utf8' }).trim() || fallback;
  } catch {
    return fallback;
  }
}

export function getBuildStatus() {
  const buildCommit = process.env.GITHUB_SHA || gitValue(['rev-parse', 'HEAD'], 'unknown');
  const builtAt = process.env.FINER_BUILD_TIME || gitValue(['show', '-s', '--format=%cI', 'HEAD'], new Date(0).toISOString());
  const releases = releaseCatalog.releases || [];
  const latestReleasePeriod = releases
    .map((release) => release.latestPeriod)
    .filter(Boolean)
    .sort()
    .at(-1) || null;
  const ageDays = latestReleasePeriod
    ? Math.max(0, Math.floor((Date.parse(builtAt) - Date.parse(latestReleasePeriod)) / 86_400_000))
    : null;

  return {
    schemaVersion: 'project-finer-status-v1',
    build: {
      commit: buildCommit,
      commitUrl: buildCommit === 'unknown' ? null : `https://github.com/ksabhinav/projectfiner/commit/${buildCommit}`,
      builtAt,
    },
    release: {
      latestPeriod: latestReleasePeriod,
      ageDays,
      freshnessTargetDays: FRESHNESS_TARGET_DAYS,
      freshnessStatus: ageDays === null ? 'unknown' : ageDays <= FRESHNESS_TARGET_DAYS ? 'within-target' : 'overdue',
      catalogUrl: 'https://projectfiner.com/releases/index.json',
    },
    monitoring: {
      cadence: 'daily',
      workflowUrl: 'https://github.com/ksabhinav/projectfiner/actions/workflows/site-monitor.yml',
      checks: ['core pages return HTTP 200', 'deployed commit matches main', 'release freshness target'],
    },
  };
}
