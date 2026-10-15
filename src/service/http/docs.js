/* Local-only Swagger UI. Never round-trip authoritative responses through JSON.parse. */
'use strict';
let rawResponse = '';
const rawPanel = document.getElementById('raw-response');
const download = document.getElementById('download-response');
download.addEventListener('click', () => {
  const url = URL.createObjectURL(new Blob([rawResponse], {type: 'application/json'}));
  const link = document.createElement('a');
  link.href = url; link.download = 'vectornext-response.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
window.ui = SwaggerUIBundle({
  url: '/openapi.json', dom_id: '#swagger-ui', validatorUrl: null,
  queryConfigEnabled: false, deepLinking: true, persistAuthorization: false,
  syntaxHighlight: {activated: false}, displayRequestDuration: true,
  requestInterceptor: request => {
    const url = new URL(request.url, window.location.href);
    if (url.origin !== window.location.origin) throw new Error('Only this local API is allowed');
    request.headers['X-VectorNext-Client'] = '1';
    return request;
  },
  responseInterceptor: response => {
    if (new URL(response.url, window.location.href).pathname !== '/openapi.json') {
      rawResponse = typeof response.text === 'string' ? response.text : '';
      rawPanel.textContent = rawResponse;
      download.disabled = !rawResponse;
      document.getElementById('exact-response').open = true;
    }
    return response;
  },
  // Swagger's default JSON renderer can parse/reformat numbers. Display the
  // original response string for every operation and use textContent via React.
  plugins: [() => ({wrapComponents: {responseBody: (_Original, system) => props =>
    typeof props.content === 'string'
      ? system.React.createElement('pre', {className: 'exact-response-body'}, props.content)
      : system.React.createElement(_Original, props)}})],
  presets: [SwaggerUIBundle.presets.apis], layout: 'BaseLayout'
});
