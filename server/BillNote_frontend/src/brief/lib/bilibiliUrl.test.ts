import { describe, expect, it } from 'vitest'
import { normalizeBilibiliInput } from './bilibiliUrl'

describe('normalizeBilibiliInput', () => {
  it('keeps a full Bilibili video URL and extracts the BV id', () => {
    expect(
      normalizeBilibiliInput(
        'https://www.bilibili.com/video/BV1xx411c7mD?p=2&vd_source=test',
      ),
    ).toEqual({
      url: 'https://www.bilibili.com/video/BV1xx411c7mD?p=2&vd_source=test',
      bvid: 'BV1xx411c7mD',
    })
  })

  it('adds a scheme to a Bilibili URL pasted without one', () => {
    expect(
      normalizeBilibiliInput('www.bilibili.com/video/BV1xx411c7mD'),
    ).toEqual({
      url: 'https://www.bilibili.com/video/BV1xx411c7mD',
      bvid: 'BV1xx411c7mD',
    })
  })

  it('accepts b23.tv short links without inventing a BV id', () => {
    expect(normalizeBilibiliInput('b23.tv/AbCdEf')).toEqual({
      url: 'https://b23.tv/AbCdEf',
      bvid: null,
    })
  })

  it('turns a bare BV id into a canonical video URL', () => {
    expect(normalizeBilibiliInput('BV1xx411c7mD')).toEqual({
      url: 'https://www.bilibili.com/video/BV1xx411c7mD',
      bvid: 'BV1xx411c7mD',
    })
  })

  it('rejects unsupported domains and blank input', () => {
    expect(normalizeBilibiliInput('https://example.com/video/123')).toEqual({
      url: '',
      bvid: null,
    })
    expect(normalizeBilibiliInput('   ')).toEqual({ url: '', bvid: null })
  })
})
