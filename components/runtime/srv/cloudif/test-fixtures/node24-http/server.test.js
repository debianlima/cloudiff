import test from 'node:test';
import assert from 'node:assert/strict';
test('node major 24',()=>assert.equal(process.versions.node.split('.')[0],'24'));
