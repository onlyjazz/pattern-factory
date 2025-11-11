// test-api.js
async function testFetchDDTItems() {
	try {
		const response = await fetch('http://127.0.0.1:8000/read_ddt_items');
		if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
		const data = await response.json();
		console.log('Fetched items:', data);
	} catch (error) {
		console.error('Error testing API:', error);
	}
}

testFetchDDTItems();
