function c(o,a){const r=new EventSource("/logs");return r.onmessage=e=>{try{const t=JSON.parse(e.data);o(t)}catch{o(e.data)}},r.onerror=e=>{},()=>r.close()}export{c};
