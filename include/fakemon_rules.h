#ifndef FAKEMON_RULES_H
#define FAKEMON_RULES_H
/* Portable arithmetic also exercised by the host regression test. */
static unsigned int FakemonMapExpProgress(unsigned int exp, unsigned int oldLo, unsigned int oldHi, unsigned int newLo, unsigned int newHi) {
    unsigned int progress;
    if (exp <= oldLo || oldHi <= oldLo || newHi <= newLo) return newLo;
    progress = exp - oldLo;
    if (progress >= oldHi - oldLo) progress = oldHi - oldLo - 1;
    /* At levels1-99 the largest product is below2^32 for these curves. */
    return newLo + progress * (newHi - newLo) / (oldHi - oldLo);
}
#endif
