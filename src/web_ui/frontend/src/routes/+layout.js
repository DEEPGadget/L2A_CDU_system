// adapter-static needs prerender to know to emit each route as a .html file.
export const prerender = true;
// Disable SSR-only behaviour like reading request headers — keeps the
// output purely static so FastAPI can serve build/ with no Node runtime.
export const ssr = false;
export const trailingSlash = 'always';
