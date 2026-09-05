<script>
	let title = $state('Test Song');

	let source = $state(
		'C:\\Users\\richr\\Downloads\\dirtyDiaperz-fadr-fixes\\dirtyDiaperz-fadr-fixes\\test.wav'
	);

	let output = $state(
		'C:\\Users\\richr\\Downloads\\dirtyDiaperz-fadr-fixes\\dirtyDiaperz-fadr-fixes\\reaper-projects\\Test Song'
	);

	let result = $state(null);
	let working = $state(false);

	async function processSong() {
		console.log('BUTTON CLICKED');

		working = true;
		result = null;

		try {
			const response = await fetch(
				'http://127.0.0.1:5001/process-song',
				{
					method: 'POST',
					headers: {
						'Content-Type': 'application/json'
					},
					body: JSON.stringify({
						title,
						source,
						out: output
					})
				}
			);

			result = await response.json();

			console.log(result);
		} catch (err) {
			console.error(err);

			result = {
				error: String(err)
			};
		}

		working = false;
	}
</script>

<h1>Dirty Diaperz Automation</h1>

<label for="title">Song Title</label>
<input id="title" bind:value={title} />

<label for="source">Source Audio File</label>
<input id="source" bind:value={source} />

<label for="output">Output Folder</label>
<input id="output" bind:value={output} />

<br /><br />

<button onclick={processSong} disabled={working}>
	{working ? 'Processing...' : 'Generate Project'}
</button>

{#if result}
	<h2>Result</h2>
	<pre>{JSON.stringify(result, null, 2)}</pre>
{/if}