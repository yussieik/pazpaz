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
    <!-- Page Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-slate-900">Payment Settings</h1>
      <p class="mt-2 text-sm text-slate-600">
        Configure payment processing to accept payments from clients directly through
        PazPaz
      </p>
    </div>

    <!-- Payment Settings Component -->
    <PaymentSettings />
  </div>
</template>
