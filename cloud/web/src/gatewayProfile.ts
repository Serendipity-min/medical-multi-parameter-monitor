export const fiveAppliance = import.meta.env?.MODE === 'five-appliance';
export const defaultGateway = fiveAppliance ? 'GW-B5-001' : 'GW-DEV-001';
