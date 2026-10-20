/* Exact rational counterexample calculator. MIT, Wei Meng Soh, 2026. */
'use strict';
(function () {
  function gcd(a, b) {
    while (b !== 0n) { const r = a % b; a = b; b = r; }
    return a < 0n ? -a : a;
  }
  function roundEven(n, d) {
    const sign = n < 0n ? -1n : 1n;
    const value = n < 0n ? -n : n;
    let q = value / d;
    const r = value % d;
    if (2n * r > d || (2n * r === d && q % 2n === 1n)) q += 1n;
    return sign * q;
  }
  function calculate(bits, n, mask) {
    if (!Number.isInteger(bits) || bits < 3 || bits > 16 ||
        !Number.isInteger(n) || n < 4 || n > 4096 || (n & (n - 1)) ||
        !Number.isInteger(mask) || mask < 0 || mask > 7) {
      throw new RangeError('Unsupported bit width, dimension, or sign pattern');
    }
    const k = (1n << BigInt(bits - 1)) - 1n;
    const peak = k + 2n;
    const signs = [0, 1, 2].map(i => mask & (1 << i) ? -1n : 1n);
    let numerator = 0n;
    for (let j = 0; j < n; j++) {
      const u = k * signs[0] + signs[1] * (j & 1 ? -1n : 1n) +
        signs[2] * (j & 2 ? -1n : 1n);
      const code = roundEven(k * u, peak);
      const residual = code * peak - k * u;
      numerator += residual * residual;
    }
    const denominator = BigInt(n) * k * k * (k * k + 2n);
    const divisor = gcd(numerator, denominator);
    return {
      fraction: `${numerator / divisor}/${denominator / divisor}`,
      errorPercent: 100 * Number(numerator) / Number(denominator),
      peakRatio: Number(peak) / (Number(k) * Math.sqrt(n)),
      originalPeak: Number(k), rotatedPeak: Number(peak) / Math.sqrt(n)
    };
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { calculate, roundEven };
  if (typeof document !== 'undefined') {
    const ids = ['family-bits', 'family-n', 'family-signs'];
    function update() {
      const values = ids.map(id => Number(document.getElementById(id).value));
      const r = calculate(...values);
      document.getElementById('family-fraction').textContent = r.fraction;
      document.getElementById('family-error').textContent = r.errorPercent.toPrecision(7) + '%';
      document.getElementById('family-peak').textContent = r.originalPeak + ' → ' + r.rotatedPeak.toPrecision(7);
      document.getElementById('family-ratio').textContent = (100 * r.peakRatio).toFixed(3) + '% of the original peak';
    }
    ids.forEach(id => document.getElementById(id).addEventListener('change', update));
    update();
  }
})();
