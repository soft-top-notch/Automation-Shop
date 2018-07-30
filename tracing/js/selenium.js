window.__tra_simulateClick = function(elem) {
    var rect = elem.getBoundingClientRect(), // holds all position- and size-properties of element
        topEnter = rect.top,
        leftEnter = rect.left, // coordinates of elements topLeft corner
        topMid = topEnter + rect.height / 2,
        leftMid = topEnter + rect.width / 2, // coordinates of elements center
        ddelay = (rect.height + rect.width) * 2, // delay depends on elements size
        ducInit = {bubbles: true, clientX: leftMid, clientY: topMid}, // create init object
        // set up the four events, the first with enter-coordinates,
        mover = new MouseEvent('mouseover', {bubbles: true, clientX: leftEnter, clientY: topEnter}),
        // the other with center-coordinates
        mdown = new MouseEvent('mousedown', ducInit),
        mup = new MouseEvent('mouseup', ducInit),
        mclick = new MouseEvent('click', ducInit);
    // trigger mouseover = enter element at toLeft corner
    elem.dispatchEvent(mover);
    // trigger mousedown  with delay to simulate move-time to center
    window.setTimeout(function() {elem.dispatchEvent(mdown)}, ddelay);
    // trigger mouseup and click with a bit longer delay
    // to simulate time between pressing/releasing the button
    window.setTimeout(function() {
        elem.dispatchEvent(mup); elem.dispatchEvent(mclick);
    }, ddelay * 1.2);
}

window.__tra_sleep = function(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

window.__tra_extractComboValues = async function(left ,top, height) {
	x = left + 1;
	y = top + 1;
	combo = document.elementFromPoint(x, y);
	if(combo.tagName === 'SELECT') {
		found = combo.options;
	}
	else {
		// open
		__tra_simulateClick(combo);
		await __tra_sleep(500);
		elem = document.elementFromPoint(x, y + height);
		while (true) {
			var rect = elem.parentNode.getBoundingClientRect();
			if (rect.x >=left && rect.y >= top) {
				elem = elem.parentNode;
			}
			else {
				break;
			}
		}
		found = elem.querySelectorAll('li');
        // close
		__tra_simulateClick(combo);		
		await __tra_sleep(500);
	}
	result = []
	for (var i = 0; i < found.length; i++) {
		result.push(found[i].textContent);
	}

	return result;
}

