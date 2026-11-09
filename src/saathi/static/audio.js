'use strict';
// Shared, dependency-free audio utilities. Provider calls remain in app.js/backend.
const SaathiAudio = (() => {
  function splitSpeech(text, limit = 850) {
    const chunks = [];
    let rest = text.trim();
    while (rest.length > limit) {
      let end = rest.lastIndexOf(' ', limit);
      if (end < limit / 2) end = limit;
      // Avoid splitting a Unicode surrogate pair.
      if (/[\uD800-\uDBFF]/.test(rest[end - 1])) end--;
      chunks.push(rest.slice(0, end).trim());
      rest = rest.slice(end).trim();
    }
    if (rest) chunks.push(rest);
    return chunks;
  }

  function wavEncode(samples, sampleRate = 16000) {
    const bytes = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(bytes);
    const str = (offset, s) => { for (let i = 0; i < s.length; i++) view.setUint8(offset + i, s.charCodeAt(i)); };
    str(0, 'RIFF'); view.setUint32(4, 36 + samples.length * 2, true); str(8, 'WAVE'); str(12, 'fmt ');
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true); str(36, 'data'); view.setUint32(40, samples.length * 2, true);
    samples.forEach((value, i) => {
      const x = Math.max(-1, Math.min(1, Number.isFinite(value) ? value : 0));
      view.setInt16(44 + i * 2, x < 0 ? x * 0x8000 : x * 0x7fff, true);
    });
    return new Blob([bytes], {type: 'audio/wav'});
  }

  function localDateValue(iso) {
    const date = new Date(iso);
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  }
  return {splitSpeech, wavEncode, localDateValue};
})();
if (typeof module !== 'undefined') module.exports = SaathiAudio;
