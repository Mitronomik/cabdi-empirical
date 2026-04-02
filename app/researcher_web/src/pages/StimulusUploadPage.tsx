import React, { useState } from 'react'
import { uploadStimuli } from '../lib/api'

export function StimulusUploadPage() {
  const [result, setResult] = useState<string>('')

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const formEl = e.currentTarget
    const form = new FormData(formEl)
    const json = await uploadStimuli(form)
    setResult(JSON.stringify(json, null, 2))
  }

  return (
    <section>
      <h2>Stimulus Upload</h2>
      <form onSubmit={onSubmit}>
        <input name="name" placeholder="stimulus set name" required />
        <select name="source_format" defaultValue="jsonl">
          <option value="jsonl">jsonl</option>
          <option value="csv">csv</option>
        </select>
        <input name="file" type="file" required />
        <button type="submit">Upload</button>
      </form>
      <pre>{result}</pre>
    </section>
  )
}
