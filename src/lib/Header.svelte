<script lang="ts">
    import { selectedStudy } from '$lib/selectedStudy';
    // Notification count - eventually takes actual notification props
    let notificationCount = 10;
    
    // Dropdown state
    let isDropdownOpen = false;

    // Dropdown items
    const dropdownItems = [
        { href: '/profile', label: 'Profile' },
        { href: '/cards', label: 'Cards' },
        { href: '/settings', label: 'Settings' },
        { href: '/help', label: 'Help and Support' },
        { href: '/pattern-factory-setup', label: 'Pattern Factory Setup' },
        { href: '#', label: 'Logout' },
    ];
    
    // Toggle dropdown menu
    function toggleDropdown() {
        isDropdownOpen = !isDropdownOpen;
    }
    
    // Close dropdown when clicking outside
    function handleClickOutside(event: MouseEvent) {
        const target = event.target as HTMLElement;
        if (!target.closest('.top-nav__item')) {
            isDropdownOpen = false;
        }
    }
    
    // Add click outside listener
    function setNode(node: HTMLElement) {
        document.addEventListener('click', handleClickOutside, true);
        return {
            destroy() {
                document.removeEventListener('click', handleClickOutside, true);
            }
        };
    }
</script>

<header class="page-header" data-tauri-drag-region>
    <div class="grid-row">
        <div class="grid-col grid-col_12">
            {#if $selectedStudy}
                <header class="heading heading_4">{$selectedStudy?.name}</header>
            {:else}
                <header class="heading heading_4">No Study Selected</header>
            {/if}
        </div>
        <div class="grid-col grid-col_12 tar fs0">
            <div class="top-nav">
                <div class="top-nav__item">
                    <a href="/actions/alerts" class="top-nav__link" data-tauri-drag-region="false" title="Data review">
                        <span class="material-icons">notifications</span>
                        <span class="top-nav__count">{notificationCount}</span>
                    </a>
                </div>
                <div class="top-nav__item" use:setNode>
                    <a href="#" class="top-nav__link" data-tauri-drag-region="false" on:click|preventDefault={toggleDropdown}>
                        <span class="material-icons">menu</span>
                    </a>
                    <div class="top-nav__drop" class:active={isDropdownOpen} data-tauri-drag-region="false">
                        {#each dropdownItems as item}
                            <a href={item.href}>{item.label}</a>
                        {/each}
                    </div>
                </div>
            </div>
        </div>
    </div>
</header>

<style>
    @import "../main.css";

    .top-nav {
        margin: 0 -1rem;
    }
    
    .top-nav__item {
        position: relative;
        display: inline-block;
        vertical-align: top;
    }
    
    .top-nav__link {
        position: relative;
        z-index: 1;
        padding: 0 1rem;
        line-height: 64px;
        transition-duration: 0.225s;
        display: inline-block;
    }
    
    .top-nav__link .material-icons {
        font-size: 24px;
        color: inherit;
        vertical-align: middle;
    }
    
    .top-nav__count {
        position: absolute;
        z-index: 1;
        top: 16px;
        right: 12px;
        width: 1rem;
        height: 1rem;
        border-radius: 50%;
        background-color: #f44336;
        font-size: 0.625rem;
        line-height: 1rem;
        text-align: center;
        pointer-events: none;
        color: #fff;
        font-style: normal;
    }
    
    .top-nav__drop {
        position: absolute;
        top: 100%;
        right: 0;
        padding: 8px 0;
        background-color: #fff;
        box-shadow: 0 0 2px 0 rgba(0,0,0,0.14), 0 2px 2px 0 rgba(0,0,0,0.12), 0 1px 3px 0 rgba(0,0,0,0.20);
        text-align: left;
        white-space: nowrap;
        visibility: hidden;
        pointer-events: none;
        opacity: 0;
        transition-duration: 0.225s;
        min-width: 200px;
        border-radius: 4px;
        z-index: 1000;
    }
    
    .top-nav__drop.active {
        visibility: visible;
        pointer-events: auto;
        opacity: 1;
    }
    
    .top-nav__drop a {
        display: block;
        padding: 0 16px;
        font-size: 16px;
        line-height: 48px;
        color: rgba(0,0,0,0.87);
        transition-duration: 0.225s;
        text-decoration: none;
    }
    
    .top-nav__drop a:hover {
        background-color: #eee;
    }
    
    .top-nav__item:hover .top-nav__link {
        background: #fff;
        color: #039be5;
    }
    
    .top-nav__item:hover .top-nav__drop {
        visibility: visible;
        opacity: 1;
        pointer-events: auto;
    }
</style>
