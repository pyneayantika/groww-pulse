const gplay = require('google-play-scraper');
const crypto = require('crypto');

// Get command line arguments
const appId = process.argv[2] || 'com.nextbillion.groww';
const daysBack = parseInt(process.argv[3]) || '7';

const userAgent = process.env.SCRAPER_USER_AGENT ||
  'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36';

// Calculate cutoff date
const cutoff = new Date();
cutoff.setDate(cutoff.getDate() - daysBack);

// Fetch reviews
gplay.memoized().reviews({
  appId: appId,
  lang: 'en',
  country: 'in',
  sort: gplay.sort.NEWEST,
  num: 200,
  headers: { 'User-Agent': userAgent }
}).then(({data}) => {
  // Filter reviews by date
  const filtered = data.filter(r => new Date(r.date) >= cutoff);
  
  // Map to required format
  const mapped = filtered.map(r => {
    const dateStr = new Date(r.date).toISOString().split('T')[0];
    return {
      review_id: crypto.createHash('sha256')
        .update('android' + String(r.id) + dateStr).digest('hex'),
      store: 'android',
      rating: r.score,
      title: r.title || '',
      text: r.text || '',
      date: dateStr,
      app_version: r.version || '',
      raw_id: String(r.id)
    };
  });
  
  // Output JSON
  console.log(JSON.stringify(mapped));
  
}).catch(err => {
  // Write error to stderr and exit with error code
  process.stderr.write(err.message);
  process.exit(1);
});
