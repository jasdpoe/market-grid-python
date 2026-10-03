import test from 'node:test';
import assert from 'node:assert/strict';
import { compressPoints } from '../market_grid/web/charts.js';

const points = Array.from({length:251},(_,i) => ({time:1700000000+i*86400,
  open:i,high:i+3,low:i-1,close:i+2,volume:10,sma:i,rsi:50,upper:i+4,lower:i-4}));

test('short ranges are not altered',() => {
  const short = points.slice(0,90);
  assert.equal(compressPoints(short),short);
});
test('long ranges retain first and last periods without truncation',() => {
  const result = compressPoints(points);
  assert.ok(result.length <= 140);
  assert.equal(result[0].startTime,points[0].time);
  assert.equal(result.at(-1).time,points.at(-1).time);
  assert.equal(result.reduce((sum,p) => sum+p.count,0),points.length);
});
test('OHLC is aggregated, indicators come from the last original candle',() => {
  const result = compressPoints(points);
  assert.equal(result[0].open,points[0].open);
  assert.equal(result[0].close,points[1].close);
  assert.equal(result[0].high,points[1].high);
  assert.equal(result[0].low,points[0].low);
  assert.equal(result[0].sma,points[1].sma);
  assert.equal(result.reduce((sum,p) => sum+p.volume,0),2510);
});
