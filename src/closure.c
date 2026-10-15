/* closure.c: the closure routines of fdlib.FDSet in C (compiled by fdlib on first import, loaded with ctypes).
   Both return the same results as the Python implementations in fdlib, which remain the reference. */
#include <stdint.h>

/* closure of C under FDs grouped by left-hand side (lhs[i] -> rhs[i], attribute sets as bitmasks):
   passes over the groups until none adds an attribute */
uint64_t closure_groups(const uint64_t *lhs, const uint64_t *rhs, int m, uint64_t C) {
    int changed = 1;
    while (changed) {
        changed = 0;
        for (int i = 0; i < m; i++)
            if ((lhs[i] & ~C) == 0 && (rhs[i] & ~C) != 0) { C |= rhs[i]; changed = 1; }
    }
    return C;
}

/* FDSet.closure_without step for step: the linear-time closure of X under the atomic FDs lhs[i] -> rhs[i]
   whose flag dis[i] is zero. The FDs with attribute a in their left-hand side are idx[start[a]] ..
   idx[start[a+1]-1] in increasing order, those with an empty left-hand side empty[0] .. empty[ne-1].
   The indices of the FDs that add an attribute are written to rec in firing order and their number to *nrec.
   cnt holds m integers and stack n integers of scratch space. */
uint64_t closure_without(int n, int m, const uint64_t *lhs, const int32_t *rhs, const int32_t *size,
                         const int32_t *start, const int32_t *idx, const int32_t *empty, int ne,
                         const uint8_t *dis, uint64_t X, int32_t *cnt, int32_t *stack, int32_t *rec, int32_t *nrec) {
    uint64_t C = X;
    int sp = 0, k = 0;
    for (int i = 0; i < m; i++)
        cnt[i] = size[i];
    for (int a = 0; a < n; a++)
        if ((X >> a) & 1)
            stack[sp++] = a;
    for (int j = 0; j < ne; j++) {
        int i = empty[j], r = rhs[i];
        if (!dis[i] && !((C >> r) & 1)) {
            C |= 1ULL << r;
            stack[sp++] = r;
            rec[k++] = i;
        }
    }
    while (sp) {
        int a = stack[--sp];
        for (int j = start[a]; j < start[a + 1]; j++) {
            int i = idx[j];
            if (--cnt[i] == 0 && !dis[i]) {
                int r = rhs[i];
                if (!((C >> r) & 1)) {
                    C |= 1ULL << r;
                    stack[sp++] = r;
                    rec[k++] = i;
                }
            }
        }
    }
    *nrec = k;
    return C;
}
