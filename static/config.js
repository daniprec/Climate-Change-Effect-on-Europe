const mortalityColour = v => {
    if (v < 0)   return '#000000';   // black
    if (v < 40)   return '#66c2a5';   // light blue
    if (v < 80)  return '#abdda4';   // teal
    if (v < 120)  return '#e6f598';   // light green
    if (v < 160)  return '#fee08b';   // yellow
    if (v < 200)  return '#fdae61';   // orange
    return '#d7191c';                // red
};

const populationDensityColour = v => {
    if (v < 0)   return '#000000';   // black
    if (v < 50) return '#000066';   // IE dark blue
    if (v < 100) return '#47bfff';   // IE light blue
    if (v < 200) return '#e6f598';   // mixed blue to green
    return '#6dc201';                // IE green
};

/* --- shared, step-wise palette for all temperature metrics ------------- */
const tempColour = v => {
    if (v < -90) return '#000000';   // black
    if (v < 0)   return '#2b83ba';   // deep blue
    if (v < 5)   return '#66c2a5';   // light blue
    if (v < 10)  return '#abdda4';   // teal
    if (v < 15)  return '#e6f598';   // light green
    if (v < 20)  return '#fee08b';   // yellow
    if (v < 25)  return '#fdae61';   // orange
    return '#d7191c';                // red (≥ 25 °C)
};

/* --- Ozone colour palette, based on WHO guidelines ------------- */
const O3Colour = v => {
    if (v < -90) return '#000000';   // black
    if (v < 50)   return '#6dc201';  // IE green (Good)
    if (v < 100)  return '#47bfff';   // IE light blue (Moderate)
    if (v < 150)  return '#fee08b';   // yellow (Unhealthy)
    if (v < 200)  return '#d7191c';   // red (Very unhealthy)
    return '#800026';  // purple (Dangerous)
}

/* --- NOx colour palette, based on WHO guidelines ------------- */
const NOxColour = v => {
    if (v < -90) return '#000000';   // black
    if (v < 10)   return '#6dc201';  // IE green (Good)
    if (v < 20)  return '#47bfff';   // IE light blue (Moderate)
    if (v < 30)  return '#fee08b';   // yellow (Unhealthy)
    if (v < 40)  return '#d7191c';   // red (Very unhealthy)
    return '#800026';  // purple (Dangerous)
}

/* --- pm10 colour palette, based on WHO guidelines ------------- */
const pm10Colour = v => {
    if (v < -90) return '#000000';   // black
    if (v < 20)   return '#6dc201';  // IE green (Good)
    if (v < 30)  return '#47bfff';   // IE light blue (Moderate)
    if (v < 50)  return '#fee08b';   // yellow (Unhealthy)
    if (v < 70)  return '#d7191c';   // red (Very unhealthy)
    return '#800026';  // purple (Dangerous)
}

const mortality_rate = {
    label : 'Mortality (per 100 k)',
    value : p => p.mortality_rate ?? -99,
    colour: mortalityColour,
    range : [2000, 2024],
    description: [
    '• WEEKLY all-cause deaths per 100 000 inhabitants. This value is derived by dividing the number of deaths in a week by the population of the region, and multiplying by 100 000 (grouping by sex and age when necessary).',
    '• Source: Eurostat - "demo_r_mwk3_20".',
    '• Spatial resolution: NUTS-3 (district).',
    '• Coverage: 2000 - 2024 (weekly).'
    ],
    url: 'https://doi.org/10.2908/DEMO_R_MWK3_20',
    colorbarStops: [[0, "#ffffcc"], [0.5, "#fd8d3c"], [1, "#800026"]],
    colorbarMin: "0",
    colorbarMax: "200",
    units: 'deaths per 100,000'
}

export const METRIC_CFG = {
    mortality_rate: mortality_rate,
    mortality_rate_T_00: { ...mortality_rate, value: p => p.mortality_rate_T_00 ?? -99 },
    mortality_rate_M_00: { ...mortality_rate, value: p => p.mortality_rate_M_00 ?? -99 },
    mortality_rate_F_00: { ...mortality_rate, value: p => p.mortality_rate_F_00 ?? -99 },
    mortality_rate_T_20: { ...mortality_rate, value: p => p.mortality_rate_T_20 ?? -99 },
    mortality_rate_M_20: { ...mortality_rate, value: p => p.mortality_rate_M_20 ?? -99 },
    mortality_rate_F_20: { ...mortality_rate, value: p => p.mortality_rate_F_20 ?? -99 },
    mortality_rate_T_40: { ...mortality_rate, value: p => p.mortality_rate_T_40 ?? -99 },
    mortality_rate_M_40: { ...mortality_rate, value: p => p.mortality_rate_M_40 ?? -99 },
    mortality_rate_F_40: { ...mortality_rate, value: p => p.mortality_rate_F_40 ?? -99 },
    mortality_rate_T_60: { ...mortality_rate, value: p => p.mortality_rate_T_60 ?? -99 },
    mortality_rate_M_60: { ...mortality_rate, value: p => p.mortality_rate_M_60 ?? -99 },
    mortality_rate_F_60: { ...mortality_rate, value: p => p.mortality_rate_F_60 ?? -99 },
    mortality_rate_T_80: { ...mortality_rate, value: p => p.mortality_rate_T_80 ?? -99 },
    mortality_rate_M_80: { ...mortality_rate, value: p => p.mortality_rate_M_80 ?? -99 },
    mortality_rate_F_80: { ...mortality_rate, value: p => p.mortality_rate_F_80 ?? -99 },

    population_density: {
        label : 'Population Density (km²)',
        value : p => p.population_density ?? -99,
        colour: populationDensityColour,
        range : [2000, 2023],
        description: [
        '• Annual population per km² (mid-year stock).',
        '• Source: Eurostat - "demo_r_d3dens".',
        '• Spatial resolution: NUTS-3.',
        '• Coverage: 2000 - 2023 (yearly).'
        ],
        url: 'https://doi.org/10.2908/DEMO_R_D3DENS',
        colorbarStops: [[0, "#000066"], [0.33, "#47bfff"], [0.66, "#e6f598"], [1, "#6dc201"]],
        colorbarMin: "0",
        colorbarMax: "500",
        units: 'people per km2'
    },

    temp_era5_q50: {
        label : 'Temperature (°C)',
        value : p => p.temp_era5_q50 ?? -99,
        colour: tempColour,
        range : [2000, 2025],
        description: [
        '• Mean 2-m air temperature from ERA5 reanalysis data.',
        '• Source: Copernicus Climate Change Service (C3S), variable "2m_temperature".',
        '• Spatial resolution: 0.25° (~30 km); sampled at region centroid.',
        '• Coverage: 2000 - 2025 (hourly, averaged to weekly in this dash).'
        ],
        url: 'https://cds.climate.copernicus.eu/cdsapp#!/dataset/reanalysis-era5-land?tab=form',
        colorbarStops: [[0, "#4575b4"], [0.5, "#fee090"], [1, "#d73027"]],
        colorbarMin: "-5",
        colorbarMax: "40",
        units: '°C'
    },

    temp_rcp45: {
        label : 'Temperature (°C)',
        value : p => p.temp_rcp45 ?? -99,
        colour: tempColour, 
        range : [2006, 2100],
        description: [
        '• Mean 2-m air temperature under medium-emission scenario RCP 4.5.',
        '• Source: EURO-CORDEX / ESGF, variable "tas".',
        '• Spatial resolution: 0.11° (~12 km); sampled at region centroid.',
        '• Coverage: 2006 - 2100 (monthly, interpolated to daily in this dash).'
        ],
        url: 'https://cordex.org/data-access/cordex-cmip5-data/cordex-cmip5-esgf/',
        colorbarStops: [[0, "#4575b4"], [0.5, "#fee090"], [1, "#d73027"]],
        colorbarMin: "-5",
        colorbarMax: "40",
        units: '°C'
    },

    temp_rcp85: {
        label : 'Temperature (°C)',
        value : p => p.temp_rcp85 ?? -99,
        colour: tempColour,
        range : [2006, 2100],
        description: [
        '• Mean 2-m air temperature under high-emission scenario RCP 8.5.',
        '• Source: EURO-CORDEX / ESGF, variable "tas".',
        '• Spatial resolution: 0.11° (~12 km); sampled at region centroid.',
        '• Coverage: 2006 - 2100 (monthly, interpolated to weekly for the dashboard).'
        ],
        url: 'https://cordex.org/data-access/cordex-cmip5-data/cordex-cmip5-esgf/',
        colorbarStops: [[0, "#4575b4"], [0.5, "#fee090"], [1, "#d73027"]],
        colorbarMin: "-5",
        colorbarMax: "40",
        units: '°C'
    },

    NOx: {
        label : 'Nitrogen Oxides (µg/m³)',
        value : p => p.NOx ?? -99,
        colour: NOxColour,
        range : [2000, 2025],
        description: [
        '• Weekly average NOx concentration in µg/m³.',
        '• Source: European Air Quality Portal, by the European Environment Agency (EEA).',
        '• Spatial resolution: stations spread across each region.',
        '• Coverage: 2000 - 2025 (hourly, averaged to weekly for the dashboard).'
        ],
        url: 'https://aqportal.discomap.eea.europa.eu/download-data/',
        colorbarStops: [[0, "#6dc201"], [0.25, "#47bfff"], [0.5, "#fee08b"], [0.75, "#d7191c"], [1, "#800026"]],
        colorbarMin: "0",
        colorbarMax: "50",
        units: 'µg/m3'
    },

    O3: {
        label : 'Ozone (µg/m³)',
        value : p => p.O3 ?? -99,
        colour: O3Colour,
        range : [2000, 2025],
        description: [
        '• Weekly average Ozone concentration in µg/m³.',
        '• Source: European Air Quality Portal, by the European Environment Agency (EEA).',
        '• Spatial resolution: stations spread across each region.',
        '• Coverage: 2000 - 2025 (hourly, averaged to weekly for the dashboard).'
        ],
        url: 'https://aqportal.discomap.eea.europa.eu/download-data/',
        colorbarStops: [[0, "#6dc201"], [0.25, "#47bfff"], [0.5, "#fee08b"], [0.75, "#d7191c"], [1, "#800026"]],
        colorbarMin: "0",
        colorbarMax: "200",
        units: 'µg/m3'
    },

    pm10: {
        label : 'Particle Matter (µg/m³)',
        value : p => p.pm10 ?? -99,
        colour: pm10Colour,
        range : [2000, 2025],
        description: [
        '• Weekly average pm10 concentration in µg/m³.',
        '• Source: European Air Quality Portal, by the European Environment Agency (EEA).',
        '• Spatial resolution: stations spread across each region.',
        '• Coverage: 2000 - 2025 (hourly, averaged to weekly for the dashboard).'
        ],
        url: 'https://aqportal.discomap.eea.europa.eu/download-data/',
        colorbarStops: [[0, "#6dc201"], [0.25, "#47bfff"], [0.5, "#fee08b"], [0.75, "#d7191c"], [1, "#800026"]],
        colorbarMin: "0",
        colorbarMax: "100",
        units: 'µg/m3'
    }
};