// --- Dynamic metric config from backend catalog ---

// Example color functions (can be extended or replaced by catalog info)
const defaultColour = v => '#cccccc';
const colourPalettes = {
    mortality: v => {
        if (v < 0)   return '#000000';
        if (v < 40)   return '#66c2a5';
        if (v < 80)  return '#abdda4';
        if (v < 120)  return '#e6f598';
        if (v < 160)  return '#fee08b';
        if (v < 200)  return '#fdae61';
        return '#d7191c';
    },
    population: v => {
        if (v < 0)   return '#000000';
        if (v < 50) return '#000066';
        if (v < 100) return '#47bfff';
        if (v < 200) return '#e6f598';
        return '#6dc201';
    },
    temp: v => {
        if (v < -90) return '#000000';
        if (v < 0)   return '#2b83ba';
        if (v < 5)   return '#66c2a5';
        if (v < 10)  return '#abdda4';
        if (v < 15)  return '#e6f598';
        if (v < 20)  return '#fee08b';
        if (v < 25)  return '#fdae61';
        return '#d7191c';
    }
};

// Build METRIC_CFG from catalog
export async function getMetricConfig() {
    const resp = await fetch('/api/catalog');
    const catalog = await resp.json();
    const cfg = {};
    for (const ds of catalog.datasets) {
        // Pick a color function based on variable name or type
        let colour = defaultColour;
        if (ds.variable.includes('mortality')) colour = colourPalettes.mortality;
        else if (ds.variable.includes('population')) colour = colourPalettes.population;
        else if (ds.variable.includes('temp')) colour = colourPalettes.temp;

        // Parse integer years from ISO date strings for slider range
        let range = undefined;
        if (ds.time_coverage && ds.time_coverage.start && ds.time_coverage.end) {
            const startYear = parseInt(ds.time_coverage.start.slice(0, 4), 10);
            const endYear = parseInt(ds.time_coverage.end.slice(0, 4), 10);
            range = [startYear, endYear];
        }

        // Build config object
        cfg[ds.variable] = {
            label: ds.display?.label || ds.variable,
            value: p => p[ds.variable] ?? -99,
            colour,
            range,
            description: ds.display?.description || [],
            url: ds.display?.url,
            colorbarStops: ds.display?.colorbarStops,
            colorbarMin: ds.display?.colorbarMin,
            colorbarMax: ds.display?.colorbarMax,
            units: ds.display?.unit_symbol || ds.display?.units
        };
    }
    return cfg;
}
