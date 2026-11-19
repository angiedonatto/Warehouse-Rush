import { defineConfig } from 'vite';

export default defineConfig({
  // .env y .env.example viven en la raíz del repo; Vite solo expone al cliente las variables VITE_*.
  envDir: '..',
});
