<script setup lang="ts">
/**
 * IconBitLogo - Bit Payment Provider Logo
 *
 * Official Bit (ביט) logo for payment provider identification.
 * Used in payment settings and configuration screens.
 *
 * Usage:
 *   <IconBitLogo class="h-8 w-8" />
 *   <IconBitLogo class="h-12 w-12" />
 */

interface Props {
  /**
   * Size of the logo (applies to both width and height)
   * @default undefined (controlled by class)
   */
  size?: number | string
}

withDefaults(defineProps<Props>(), {
  size: undefined,
})
</script>

<template>
  <svg
    viewBox="0 0 1080 1080"
    xmlns="http://www.w3.org/2000/svg"
    :width="size"
    :height="size"
    aria-label="Bit payment logo"
    role="img"
  >
    <!-- Dark teal/cyan rounded square background -->
    <rect width="1080" height="1080" rx="200" fill="#0A4D4D" />

    <!-- Cyan "bit" text with dot on 'i' -->
    <g fill="#5DFDFD">
      <!-- Letter 'b' -->
      <path
        d="M150,320 L220,320 L220,820 C220,830 215,835 205,835 L165,835 C155,835 150,830 150,820 Z"
      />
      <path
        d="M220,550 C220,480 270,430 340,430 C410,430 460,480 460,550 L460,700 C460,770 410,820 340,820 C270,820 220,770 220,700 Z M300,700 C300,730 315,745 340,745 C365,745 380,730 380,700 L380,550 C380,520 365,505 340,505 C315,505 300,520 300,550 Z"
      />

      <!-- Letter 'i' with dot -->
      <circle cx="582" cy="360" r="40" />
      <rect x="542" y="450" width="80" height="385" rx="10" />

      <!-- Letter 't' -->
      <path
        d="M680,320 L760,320 L760,450 L850,450 L850,510 L760,510 L760,750 C760,770 770,780 790,780 L850,780 L850,835 L790,835 C730,835 680,805 680,745 Z"
      />
      <rect x="680" y="450" width="170" height="60" rx="10" />
    </g>
  </svg>
</template>
