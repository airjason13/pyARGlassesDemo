#include <stdint.h>

#if defined(__aarch64__) || defined(__ARM_NEON)
#include <arm_neon.h>
#define DEMURA_USE_NEON 1
#else
#define DEMURA_USE_NEON 0
#endif
/*------------------------------------
x86:
gcc -O3 -shared -fPIC \
    demura_transform.c \
    demura_neon.c \
    -o libgstdemura.so
------------------------------------
ARM：
gcc -O3 -shared -fPIC \
    -march=armv8-a \
    demura_transform.c \
    demura_neon.c \
    -o libgstdemura.so
 ------------------------------------*/
void demura_process_neon(
    uint8_t *frame,
    const uint16_t *gain,
    int frame_stride,
    int x_min,
    int y_min,
    int x_max,
    int y_max
)
{
    const int roi_w = x_max - x_min;
    const int roi_h = y_max - y_min;

#if DEMURA_USE_NEON

    // =============================================
    // ARM / i.MX93 NEON
    // =============================================

    for (int y = 0; y < roi_h; y++)
    {
        uint8_t *pixel_ptr =
            frame +
            (y_min + y) * frame_stride + x_min * 3;

        const uint16_t *gain_ptr =
            gain +
            y * roi_w * 3;

        int count = roi_w * 3;
        int i = 0;

        for (; i <= count - 8; i += 8)
        {
            uint8x8_t pixels =
                vld1_u8(pixel_ptr + i);

            uint16x8_t gains =
                vld1q_u16(gain_ptr + i);

            uint16x8_t pixel16 =
                vmovl_u8(pixels);

            uint32x4_t mul_low =
                vmull_u16(
                    vget_low_u16(pixel16),
                    vget_low_u16(gains)
                );

            uint32x4_t mul_high =
                vmull_u16(
                    vget_high_u16(pixel16),
                    vget_high_u16(gains)
                );

            uint16x4_t shift_low =
                vshrn_n_u32(mul_low, 8);

            uint16x4_t shift_high =
                vshrn_n_u32(mul_high, 8);

            uint16x8_t result16 =
                vcombine_u16(
                    shift_low,
                    shift_high
                );

            uint8x8_t result8 =
                vqmovn_u16(result16);

            vst1_u8(
                pixel_ptr + i,
                result8
            );
        }

        // Remaining pixels
        for (; i < count; i++)
        {
            uint32_t value =
                (uint32_t)pixel_ptr[i]
                * (uint32_t)gain_ptr[i];

            value >>= 8;

            if (value > 255)
                value = 255;

            pixel_ptr[i] =
                (uint8_t)value;
        }
    }

#else

    // =============================================
    // x86 / Generic C
    // =============================================

    for (int y = 0; y < roi_h; y++)
    {
        uint8_t *pixel_ptr =
            frame +
            (y_min + y) * frame_stride + x_min * 3;

        const uint16_t *gain_ptr =
            gain +
            y * roi_w * 3;

        const int count =
            roi_w * 3;

        for (int i = 0; i < count; i++)
        {
            uint32_t value =
                (uint32_t)pixel_ptr[i]
                * (uint32_t)gain_ptr[i];

            value >>= 8;

            if (value > 255)
                value = 255;

            pixel_ptr[i] =
                (uint8_t)value;
        }
    }

#endif
}
