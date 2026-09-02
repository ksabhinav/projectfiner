/**
 * Merge legacy name-keyed district payloads into one canonical LGD-backed page.
 * Conflicting values fail the build instead of being selected by file order.
 */
export function mergeDistrictData(entry, payloads) {
  if (!payloads.length) {
    throw new Error(`No data payloads for district LGD ${entry.lgdCode}`);
  }

  const indicators = new Map();
  for (const payload of payloads) {
    if (payload.state !== entry.state) {
      throw new Error(
        `Cross-state district payload for LGD ${entry.lgdCode}: ${payload.state}`,
      );
    }

    for (const [indicatorId, indicator] of Object.entries(payload.indicators || {})) {
      const existing = indicators.get(indicatorId) || {
        label: indicator.label,
        unit: indicator.unit,
        byQuarter: new Map(),
      };
      if (existing.label !== indicator.label || existing.unit !== indicator.unit) {
        throw new Error(
          `Conflicting metadata for ${indicatorId} in district LGD ${entry.lgdCode}`,
        );
      }

      for (const observation of indicator.series || []) {
        const prior = existing.byQuarter.get(observation.quarter);
        const signature = JSON.stringify([observation.value, observation.field]);
        if (prior && prior.signature !== signature) {
          throw new Error(
            `Conflicting ${indicatorId} value for LGD ${entry.lgdCode} at ${observation.quarter}`,
          );
        }
        existing.byQuarter.set(observation.quarter, { signature, observation });
      }
      indicators.set(indicatorId, existing);
    }
  }

  let latestQuarter = null;
  const mergedIndicators = {};
  for (const [indicatorId, indicator] of indicators) {
    const series = [...indicator.byQuarter.values()]
      .map(({ observation }) => observation)
      .sort((a, b) => a.quarter.localeCompare(b.quarter));
    if (!series.length) continue;
    const latest = series[series.length - 1];
    if (latestQuarter === null || latest.quarter > latestQuarter) {
      latestQuarter = latest.quarter;
    }
    mergedIndicators[indicatorId] = {
      label: indicator.label,
      unit: indicator.unit,
      latest,
      series,
    };
  }

  return {
    lgdCode: entry.lgdCode,
    stateLgdCode: entry.stateLgdCode,
    state: entry.state,
    stateLabel: entry.stateLabel,
    district: entry.district,
    districtSlug: entry.districtSlug,
    latestQuarter,
    indicators: mergedIndicators,
  };
}
