(function () {
    'use strict';

    const endpoint = '/api/philippine-locations/';

    function option(select, value, label) {
        const item = document.createElement('option');
        item.value = value;
        item.textContent = label;
        select.appendChild(item);
    }

    function clear(select, placeholder) {
        select.innerHTML = '';
        option(select, '', placeholder);
        select.value = '';
        select.disabled = true;
    }

    async function load(select, level, parentCode) {
        clear(select, select.dataset.placeholder || 'Select an option');
        if (!parentCode) return;
        select.disabled = true;
        try {
            const response = await fetch(`${endpoint}?level=${level}&parent_code=${encodeURIComponent(parentCode)}`);
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'Unable to load locations');
            data.locations.forEach(item => option(select, item.code, item.name));
            select.disabled = false;
        } catch (error) {
            select.dataset.locationError = 'true';
            console.error('Philippine address lookup failed:', error);
        }
    }

    async function initialize(container) {
        const region = container.querySelector('[data-location-level="regions"]');
        const province = container.querySelector('[data-location-level="provinces"]');
        const city = container.querySelector('[data-location-level="cities"]');
        const barangay = container.querySelector('[data-location-level="barangays"]');
        if (!region || !province || !city || !barangay) return;

        clear(region, region.dataset.placeholder || 'Select a region');
        clear(province, province.dataset.placeholder || 'Select a region first');
        clear(city, city.dataset.placeholder || 'Select a province first');
        clear(barangay, barangay.dataset.placeholder || 'Select a city/municipality first');
        region.disabled = true;

        region.addEventListener('change', async () => {
            clear(city, city.dataset.placeholder || 'Select a province first');
            clear(barangay, barangay.dataset.placeholder || 'Select a city/municipality first');
            await load(province, 'provinces', region.value);
            container.dispatchEvent(new CustomEvent('phAddressChange', { bubbles: true }));
        });
        province.addEventListener('change', async () => {
            clear(barangay, barangay.dataset.placeholder || 'Select a city/municipality first');
            await load(city, 'cities', province.value);
            container.dispatchEvent(new CustomEvent('phAddressChange', { bubbles: true }));
        });
        city.addEventListener('change', async () => {
            await load(barangay, 'barangays', city.value);
            container.dispatchEvent(new CustomEvent('phAddressChange', { bubbles: true }));
        });
        barangay.addEventListener('change', () => {
            container.dispatchEvent(new CustomEvent('phAddressChange', { bubbles: true }));
        });

        try {
            const response = await fetch(`${endpoint}?level=regions`);
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'Unable to load regions');
            data.locations.forEach(item => option(region, item.code, item.name));
            region.disabled = false;

            const selectedRegion = container.dataset.regionCode;
            const selectedProvince = container.dataset.provinceCode;
            const selectedCity = container.dataset.cityCode;
            const selectedBarangay = container.dataset.barangayCode;
            if (selectedRegion) {
                region.value = selectedRegion;
                await load(province, 'provinces', selectedRegion);
                if (selectedProvince) {
                    province.value = selectedProvince;
                    await load(city, 'cities', selectedProvince);
                    if (selectedCity) {
                        city.value = selectedCity;
                        await load(barangay, 'barangays', selectedCity);
                        if (selectedBarangay) barangay.value = selectedBarangay;
                    }
                }
            }
            container.dispatchEvent(new CustomEvent('phAddressReady', { bubbles: true }));
        } catch (error) {
            region.dataset.locationError = 'true';
            console.error('Philippine address lookup failed:', error);
        }
    }

    window.setPhilippineAddressSelection = async function (container, selection) {
        if (!container) return;
        const region = container.querySelector('[data-location-level="regions"]');
        const province = container.querySelector('[data-location-level="provinces"]');
        const city = container.querySelector('[data-location-level="cities"]');
        const barangay = container.querySelector('[data-location-level="barangays"]');
        if (!region || !province || !city || !barangay) return;
        container.dataset.regionCode = selection.region_code || '';
        container.dataset.provinceCode = selection.province_code || '';
        container.dataset.cityCode = selection.city_code || '';
        container.dataset.barangayCode = selection.barangay_code || '';
        if (region.options.length < 2) return;
        region.value = selection.region_code || '';
        clear(province, province.dataset.placeholder || 'Select a region first');
        clear(city, city.dataset.placeholder || 'Select a province first');
        clear(barangay, barangay.dataset.placeholder || 'Select a city/municipality first');
        if (region.value) {
            await load(province, 'provinces', region.value);
            province.value = selection.province_code || '';
        }
        if (province.value) {
            await load(city, 'cities', province.value);
            city.value = selection.city_code || '';
        }
        if (city.value) {
            await load(barangay, 'barangays', city.value);
            barangay.value = selection.barangay_code || '';
        }
        container.dispatchEvent(new CustomEvent('phAddressReady', { bubbles: true }));
    };

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-ph-address]').forEach(initialize);
    });
})();
