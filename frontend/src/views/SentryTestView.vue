<template>
  <div class="sentry-test">
    <h1>Sentry Test Page</h1>
    <p>Click the button to trigger a test error that Sentry should capture.</p>
    <button @click="throwError" class="error-button">Throw Test Error</button>
  </div>
</template>

<script setup lang="ts">
function throwError() {
  // This error will be thrown inside a Vue component event handler
  // Sentry should capture this because it's within the Vue app context
  throw new Error('Sentry test error from Vue component!')
}
</script>

<style scoped>
.sentry-test {
  max-width: 600px;
  margin: 50px auto;
  padding: 20px;
  text-align: center;
}

.error-button {
  margin-top: 20px;
  padding: 12px 24px;
  font-size: 16px;
  background-color: #e74c3c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.error-button:hover {
  background-color: #c0392b;
}
</style>
