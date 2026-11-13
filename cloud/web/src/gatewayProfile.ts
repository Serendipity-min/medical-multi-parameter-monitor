export const fiveAppliance = import.meta.env?.MODE === 'five-appliance';
// 默认连接真机网关；线上 Backend 只授权 GW-C-001，模拟网关不再作为默认入口（可用 ?gateway= 指定）。
export const defaultGateway = fiveAppliance ? 'GW-B5-001' : 'GW-C-001';
