<script setup lang="ts">
/**
 * Payments Settings View
 *
 * Manages payment tracking configuration for workspace.
 *
 * Phase 1: Manual payment tracking
 * - Track appointments as paid/unpaid
 * - Store bank account details for sharing with clients
 *
 * Future phases:
 * - Automated payment providers (Bit, PayBox, etc.)
 * - Automated invoicing
 * - Payment analytics
 */

import PaymentSettings from '@/components/settings/PaymentSettings.vue'
</script>

<template>
  <div>
    <!-- Payment Settings Component -->
    <PaymentSettings />
  </div>
</template>
