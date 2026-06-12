// 队伍代码（FIFA 三字码）→ ISO 3166-1 alpha-2（flagcdn 用）。
// 用国旗图片而非 emoji——Windows 系统字体不渲染区域指示符 emoji 国旗。
// 英格兰/苏格兰用 flagcdn 的子区划代码 gb-eng / gb-sct。

export const ISO2: Record<string, string> = {
  MEX: 'mx', RSA: 'za', KOR: 'kr', CZE: 'cz',
  CAN: 'ca', BIH: 'ba', QAT: 'qa', SUI: 'ch',
  BRA: 'br', MAR: 'ma', HAI: 'ht', SCO: 'gb-sct',
  USA: 'us', PAR: 'py', AUS: 'au', TUR: 'tr',
  GER: 'de', CUW: 'cw', CIV: 'ci', ECU: 'ec',
  NED: 'nl', JPN: 'jp', SWE: 'se', TUN: 'tn',
  BEL: 'be', EGY: 'eg', IRN: 'ir', NZL: 'nz',
  ESP: 'es', CPV: 'cv', KSA: 'sa', URU: 'uy',
  FRA: 'fr', SEN: 'sn', IRQ: 'iq', NOR: 'no',
  ARG: 'ar', ALG: 'dz', AUT: 'at', JOR: 'jo',
  POR: 'pt', COD: 'cd', UZB: 'uz', COL: 'co',
  ENG: 'gb-eng', CRO: 'hr', GHA: 'gh', PAN: 'pa',
}

// flagcdn PNG（w80 ≈ 视网膜屏清晰），按显示尺寸缩放
export function flagUrl(code: string | null | undefined): string | null {
  if (!code) return null
  const iso = ISO2[code]
  return iso ? `https://flagcdn.com/w80/${iso}.png` : null
}
